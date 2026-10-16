"""Lightweight speaker (voice) identification for the EON Voice module.

Design notes:
    - This is a spectral + pitch "voiceprint" — not a deep-learned
      speaker embedding model (e.g. resemblyzer, speechbrain,
      pyannote.audio). Those give meaningfully better accuracy, but
      all of them pull in `torch`, a large, CPU-heavy dependency —
      a real cost on a modest CPU-only laptop, which is exactly the
      hardware constraint already documented elsewhere in this
      project. This class instead builds a fixed-length feature vector
      from a log-spaced spectral envelope plus an estimated pitch
      (fundamental frequency), using only ``numpy`` (already a
      dependency via ``faster_whisper``) — no new package required.
    - Be upfront about what this buys: it's a genuine, real signal
      (pitch and spectral shape do meaningfully differ between
      speakers), but it is a soft, approximate check, not a robust
      biometric security boundary. Expect real false-accept and
      false-reject rates, especially on short or noisy audio. It's
      well suited to "was that probably the enrolled owner, for a
      personalized greeting" — not to gating high-risk actions. If
      stronger speaker verification is wanted later, swapping this
      class for one backed by a real embedding model is a contained
      change, since callers only depend on ``enroll``/``verify``.
    - The enrolled profile is a single averaged feature vector
      persisted to disk as a ``.npy`` file. Re-enrolling overwrites it
      (only one owner profile is supported).

Requires: Python 3.12+, numpy
"""

from __future__ import annotations

import wave
import io
from pathlib import Path

import numpy as np

_BYTES_PER_SAMPLE = 2  # 16-bit mono PCM

# Log-spaced frequency band edges (Hz) the spectral envelope is
# bucketed into. Chosen to roughly span the range where voiced speech
# carries most of its speaker-distinguishing energy (fundamental
# frequency and the first few formants), rather than a full 0-8kHz
# linear spread, which would waste bins on frequencies speech barely
# occupies.
_NUM_SPECTRAL_BANDS = 24
_MIN_FREQUENCY_HZ = 80.0
_MAX_FREQUENCY_HZ = 4000.0

# Autocorrelation-based pitch estimation range. 70-400 Hz comfortably
# covers typical adult speaking pitch (fundamental frequency), for any
# speaker/gender.
_MIN_PITCH_HZ = 70.0
_MAX_PITCH_HZ = 400.0


class SpeakerIdentifier:
    """Enrolls and verifies a single owner's voice via a lightweight
    spectral + pitch fingerprint.

    Attributes:
        _profile_path: Filesystem path the enrolled voiceprint is
            persisted to/loaded from.
        _threshold: Minimum cosine similarity for ``verify`` to
            consider a candidate a match.
    """

    def __init__(self, profile_path: str, threshold: float = 0.90) -> None:
        self._profile_path = Path(profile_path)
        self._threshold = threshold
        self._cached_profile: np.ndarray | None = None

    @property
    def is_enrolled(self) -> bool:
        """Whether an owner voiceprint has been enrolled and saved."""
        return self._profile_path.exists()

    def enroll(self, pcm_bytes: bytes, sample_rate_hz: int) -> None:
        """Computes a voiceprint from ``pcm_bytes`` and saves it as the
        owner's profile, overwriting any previously enrolled profile.

        Args:
            pcm_bytes: Raw 16-bit mono PCM audio to enroll from.
                Several seconds of clear, normal speech (not silence)
                gives the most reliable profile.
            sample_rate_hz: Sample rate the audio was captured at.

        Raises:
            ValueError: If no usable voiced audio is found in
                ``pcm_bytes`` (e.g. it's silence).
        """
        feature_vector = self._extract_features(pcm_bytes, sample_rate_hz)

        self._profile_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(self._profile_path, feature_vector)
        self._cached_profile = feature_vector

    def verify(self, pcm_bytes: bytes, sample_rate_hz: int) -> bool:
        """Checks whether ``pcm_bytes`` likely came from the enrolled owner.

        Args:
            pcm_bytes: Raw 16-bit mono PCM candidate audio.
            sample_rate_hz: Sample rate the audio was captured at.

        Returns:
            ``True`` if the candidate's voiceprint is within the
            configured similarity threshold of the enrolled profile.
            ``False`` if nothing is enrolled, or the audio has no
            usable voiced content, or it doesn't match closely enough.
        """
        if not self.is_enrolled:
            return False

        try:
            candidate = self._extract_features(pcm_bytes, sample_rate_hz)
        except ValueError:
            return False

        profile = self._load_profile()
        similarity = self._cosine_similarity(candidate, profile)

        return similarity >= self._threshold

    def _load_profile(self) -> np.ndarray:
        if self._cached_profile is None:
            self._cached_profile = np.load(self._profile_path)
        return self._cached_profile

    def _extract_features(self, pcm_bytes: bytes, sample_rate_hz: int) -> np.ndarray:
        """Builds the fixed-length voiceprint feature vector.

        Combines a log-spaced spectral envelope (captures formant/
        timbre shape) with an estimated pitch (fundamental frequency,
        one of the most individually distinctive and stable speaker
        characteristics), then L2-normalizes the result so cosine
        similarity is a meaningful comparison regardless of loudness.
        """
        samples = self._decode_pcm(pcm_bytes)

        if samples.size < sample_rate_hz // 4:
            raise ValueError("Not enough audio to extract a voiceprint from.")

        # Checked directly on the raw samples, not on the resulting
        # feature vector's norm: the pitch estimate falls back to the
        # midrange of the expected pitch band when no periodicity is
        # found (silence/noise), which keeps that fallback value
        # non-zero and would otherwise let silence slip through as a
        # "valid" (if meaningless) feature vector.
        rms = float(np.sqrt(np.mean(np.square(samples))))
        if rms < 1e-4:
            raise ValueError("Audio is silent or too quiet to extract a voiceprint from.")

        spectral_envelope = self._spectral_envelope(samples, sample_rate_hz)
        pitch_hz = self._estimate_pitch(samples, sample_rate_hz)

        # Pitch is folded in as a normalized scalar (roughly 0-1 across
        # the expected human pitch range) so it contributes
        # meaningfully alongside the spectral bands without dominating
        # or being drowned out by their differing scale.
        normalized_pitch = (pitch_hz - _MIN_PITCH_HZ) / (_MAX_PITCH_HZ - _MIN_PITCH_HZ)
        normalized_pitch = float(np.clip(normalized_pitch, 0.0, 1.0))

        feature_vector = np.concatenate(
            [spectral_envelope, np.array([normalized_pitch], dtype=np.float64)]
        )

        norm = np.linalg.norm(feature_vector)
        if norm == 0.0:
            raise ValueError("Audio produced an all-zero feature vector.")

        return feature_vector / norm

    @staticmethod
    def _decode_pcm(pcm_bytes: bytes) -> np.ndarray:
        """Decodes raw 16-bit PCM bytes (or a WAV-wrapped buffer) into
        a normalized float64 array in [-1.0, 1.0].

        Accepts either bare PCM or a full WAV container transparently,
        since callers in this codebase pass audio both ways depending
        on the code path (the wake-word listener wraps PCM as WAV
        before this point; enrollment may pass raw PCM directly).
        """
        if pcm_bytes[:4] == b"RIFF":
            with wave.open(io.BytesIO(pcm_bytes), "rb") as wav_file:
                raw = wav_file.readframes(wav_file.getnframes())
        else:
            raw = pcm_bytes

        usable_length = len(raw) - (len(raw) % _BYTES_PER_SAMPLE)
        samples = np.frombuffer(raw[:usable_length], dtype=np.int16).astype(np.float64)
        return samples / 32_768.0

    @staticmethod
    def _spectral_envelope(samples: np.ndarray, sample_rate_hz: int) -> np.ndarray:
        """Computes a log-spaced-band-averaged magnitude spectrum."""
        windowed = samples * np.hanning(len(samples))
        magnitude = np.abs(np.fft.rfft(windowed))
        freqs = np.fft.rfftfreq(len(samples), d=1.0 / sample_rate_hz)

        band_edges = np.logspace(
            np.log10(_MIN_FREQUENCY_HZ),
            np.log10(min(_MAX_FREQUENCY_HZ, sample_rate_hz / 2.0)),
            _NUM_SPECTRAL_BANDS + 1,
        )

        band_energies = np.zeros(_NUM_SPECTRAL_BANDS, dtype=np.float64)

        for i in range(_NUM_SPECTRAL_BANDS):
            mask = (freqs >= band_edges[i]) & (freqs < band_edges[i + 1])
            if np.any(mask):
                band_energies[i] = float(np.mean(magnitude[mask]))

        # log-compress, matching how humans (and speech systems)
        # perceive loudness roughly logarithmically.
        return np.log1p(band_energies)

    @staticmethod
    def _estimate_pitch(samples: np.ndarray, sample_rate_hz: int) -> float:
        """Estimates fundamental frequency via autocorrelation.

        Returns the midpoint of the valid pitch range if no clear
        periodicity is found (e.g. unvoiced/noisy audio), rather than
        raising — pitch is one signal among several here, not a hard
        requirement for a usable feature vector.
        """
        min_lag = int(sample_rate_hz / _MAX_PITCH_HZ)
        max_lag = int(sample_rate_hz / _MIN_PITCH_HZ)

        if max_lag >= len(samples):
            return (_MIN_PITCH_HZ + _MAX_PITCH_HZ) / 2.0

        windowed = samples - np.mean(samples)
        autocorr = np.correlate(windowed, windowed, mode="full")
        autocorr = autocorr[len(autocorr) // 2 :]

        search_range = autocorr[min_lag:max_lag]

        if search_range.size == 0 or np.max(search_range) <= 0:
            return (_MIN_PITCH_HZ + _MAX_PITCH_HZ) / 2.0

        best_lag = min_lag + int(np.argmax(search_range))
        return sample_rate_hz / best_lag

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0.0:
            return 0.0
        return float(np.dot(a, b) / denom)
