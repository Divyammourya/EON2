"""Faster-Whisper backed speech-to-text provider for the EON Voice module.

This module provides ``FasterWhisperProvider``, a concrete
implementation of ``SpeechToTextProvider`` backed by the
``faster-whisper`` library (a CTranslate2 reimplementation of OpenAI's
Whisper model).

Design notes:
    - ``FasterWhisperProvider`` is the only place in the Voice module
      that imports ``faster_whisper``. All other Voice components
      depend solely on the ``SpeechToTextProvider`` abstraction,
      keeping the concrete recognition library isolated behind a
      single implementation (Dependency Inversion Principle). Replacing
      Faster-Whisper with another STT engine requires writing a new
      ``SpeechToTextProvider`` implementation; no other code changes.
    - The underlying Whisper model is loaded lazily, on first use, so
      constructing this provider is cheap and side-effect free. Model
      loading is guarded by a lock using the double-checked locking
      pattern to remain safe under concurrent access.
    - Inference calls are serialized behind a dedicated lock, since the
      underlying CTranslate2 model instance is not guaranteed to be
      safe for concurrent invocation.
    - All exceptions raised by ``faster_whisper``, ``wave``, or
      ``numpy`` are caught at the boundary of this class and translated
      into the project's own exception types
      (``VoiceInitializationError``, ``SpeechRecognitionError``,
      ``VoiceSessionError``, ``VoiceProviderError``); no third-party
      exception type ever escapes this module.
    - Audio to be transcribed is expected as raw, single-channel,
      16 kHz, 16-bit PCM WAV bytes stored under the ``"audio_bytes"``
      key of ``VoiceSession.metadata``. This keeps the fixed
      ``transcribe`` / ``transcribe_stream`` signatures defined by
      ``SpeechToTextProvider`` unchanged while still allowing audio to
      be supplied per call.

Requires: Python 3.12+, faster-whisper, numpy
"""

from __future__ import annotations

import io
import math
import threading
import wave
from collections.abc import Iterator
from typing import Any
from uuid import UUID

import numpy as np
from faster_whisper import WhisperModel

from src.modules.voice.exceptions import (
    SpeechRecognitionError,
    VoiceInitializationError,
    VoiceProviderError,
    VoiceSessionError,
)
from src.modules.voice.models import (
    SpeechRecognitionResult,
    SpeechSynthesisRequest,
    VoiceSession,
)
from src.modules.voice.providers.stt import SpeechToTextProvider

_VALID_DEVICES = frozenset({"cpu", "cuda"})
_EXPECTED_SAMPLE_RATE_HZ = 16_000
_EXPECTED_CHANNELS = 1
_EXPECTED_SAMPLE_WIDTH_BYTES = 2
_PCM16_NORMALIZATION_FACTOR = 32_768.0
_DEFAULT_BEAM_SIZE = 5
_AUDIO_METADATA_KEY = "audio_bytes"


class FasterWhisperProvider(SpeechToTextProvider):
    """Speech-to-text provider backed by the ``faster-whisper`` library.

    ``FasterWhisperProvider`` transcribes raw, single-channel, 16 kHz,
    16-bit PCM WAV audio using a locally loaded Whisper model. It
    supports both single-shot transcription (``transcribe``) and
    per-segment streaming transcription (``transcribe_stream``). As a
    speech-to-text-only provider, it does not support speech synthesis;
    ``speak`` always raises ``VoiceProviderError``.

    Attributes:
        _model_name: Name or path of the Whisper model to load (e.g.
            "tiny", "base", "small", "medium", "large-v3").
        _device: Compute device the model runs on ("cpu" or "cuda").
        _compute_type: CTranslate2 compute type used for inference
            (e.g. "int8", "float16", "float32").
        _download_root: Optional directory used to cache downloaded
            model weights.
        _model: The lazily loaded ``WhisperModel`` instance, or
            ``None`` if not yet loaded.
        _load_lock: Guards lazy, thread-safe initialization of
            ``_model``.
        _inference_lock: Serializes calls into the underlying model to
            avoid concurrent inference on a single model instance.
        _active_session_ids: Identifiers of sessions currently started
            on this provider.
        _sessions_lock: Guards concurrent access to
            ``_active_session_ids``.
    """

    def __init__(
        self,
        model_name: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        download_root: str | None = None,
    ) -> None:
        """Configures the provider without loading the model yet.

        Args:
            model_name: Name or path of the Whisper model to load.
                Must be a non-empty string.
            device: Compute device to run the model on. Must be either
                "cpu" or "cuda".
            compute_type: CTranslate2 compute type used for inference
                (e.g. "int8", "float16", "float32"). Must be a
                non-empty string.
            download_root: Optional directory used to cache downloaded
                model weights. If ``None``, the library's default cache
                location is used.

        Raises:
            ValueError: If any argument fails validation.
        """
        self._validate_constructor_args(model_name, device, compute_type)
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._download_root = download_root

        self._model: WhisperModel | None = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

        self._active_session_ids: set[UUID] = set()
        self._sessions_lock = threading.Lock()

    @property
    def name(self) -> str:
        """Returns the unique, human-readable name of this provider.

        Returns:
            The literal string "faster-whisper".
        """
        return "faster-whisper"

    def initialize(self) -> None:
        """Eagerly loads the underlying Whisper model.

        Calling this method is optional: the model is loaded lazily on
        first use regardless. Calling it explicitly allows initialization
        failures to surface before any session is created.

        Raises:
            VoiceInitializationError: If the model fails to load.
        """
        self._get_model()

    def shutdown(self) -> None:
        """Releases the loaded Whisper model and clears session tracking.

        Raises:
            VoiceProviderError: If the model fails to release cleanly.
        """
        with self._load_lock:
            # try:
            self._model = None
            # except Exception as exc:
            #     raise VoiceProviderError(
            #         "Failed to release the Faster-Whisper model.",
            #         provider_name=self.name,
            #     ) from exc
        with self._sessions_lock:
            self._active_session_ids.clear()

    def health_check(self) -> bool:
        """Reports whether the provider is loaded and ready for use.

        Returns:
            ``True`` if the Whisper model has been successfully
            loaded, ``False`` otherwise.
        """
        return self._model is not None

    def start_session(self, session: VoiceSession) -> None:
        """Registers a session as active on this provider.

        Args:
            session: The canonical voice session to register.

        Raises:
            VoiceSessionError: If the session is already registered.
        """
        with self._sessions_lock:
            if session.session_id in self._active_session_ids:
                raise VoiceSessionError(
                    "Session is already active on this provider.",
                    session_id=str(session.session_id),
                )
            self._active_session_ids.add(session.session_id)

    def stop_session(self, session: VoiceSession) -> None:
        """Unregisters a session from this provider.

        Args:
            session: The canonical voice session to unregister.

        Raises:
            VoiceSessionError: If the session is not registered.
        """
        with self._sessions_lock:
            if session.session_id not in self._active_session_ids:
                raise VoiceSessionError(
                    "Session is not active on this provider.",
                    session_id=str(session.session_id),
                )
            self._active_session_ids.discard(session.session_id)

    def transcribe(self, session: VoiceSession) -> SpeechRecognitionResult:
        """Transcribes the audio associated with a session in one shot.

        Args:
            session: The voice session to transcribe audio for. The
                audio to transcribe must be present as raw PCM WAV
                bytes under ``session.metadata["audio_bytes"]``.

        Returns:
            A single, final speech recognition result containing the
            full transcript.

        Raises:
            VoiceSessionError: If the session is not registered on this
                provider.
            SpeechRecognitionError: If the audio is missing, malformed,
                or transcription otherwise fails.
            VoiceInitializationError: If the model fails to load.
        """
        self._ensure_session_active(session.session_id)
        samples = self._decode_wav_bytes(self._extract_audio_bytes(session))
        segments, info = self._run_inference(samples, session)

        segment_list = list(segments)
        transcript = " ".join(segment.text.strip() for segment in segment_list).strip()
        confidence = self._average_confidence(segment_list)

        return SpeechRecognitionResult(
            session_id=session.session_id,
            transcript=transcript,
            confidence=confidence,
            is_final=True,
            language_code=info.language or session.config.language_code,
        )

    def transcribe_stream(
        self,
        session: VoiceSession,
    ) -> Iterator[SpeechRecognitionResult]:
        """Streams transcription results for a session, one per segment.

        Args:
            session: The voice session to transcribe audio for. The
                audio to transcribe must be present as raw PCM WAV
                bytes under ``session.metadata["audio_bytes"]``.

        Yields:
            One speech recognition result per Whisper-detected speech
            segment, in chronological order. Each yielded result is
            final for its segment.

        Raises:
            VoiceSessionError: If the session is not registered on this
                provider.
            SpeechRecognitionError: If the audio is missing, malformed,
                or transcription otherwise fails.
            VoiceInitializationError: If the model fails to load.
        """
        self._ensure_session_active(session.session_id)
        samples = self._decode_wav_bytes(self._extract_audio_bytes(session))
        segments, info = self._run_inference(samples, session)

        language_code = info.language or session.config.language_code
        for segment in segments:
            yield SpeechRecognitionResult(
                session_id=session.session_id,
                transcript=segment.text.strip(),
                confidence=self._segment_confidence(segment),
                is_final=True,
                language_code=language_code,
            )

    def speak(
        self,
        session: VoiceSession,
        request: SpeechSynthesisRequest,
    ) -> None:
        """Always raises, since this provider does not support synthesis.

        Args:
            session: Unused. Present to satisfy the ``VoiceProvider``
                interface.
            request: Unused. Present to satisfy the ``VoiceProvider``
                interface.

        Raises:
            VoiceProviderError: Always. Faster-Whisper is a
                speech-to-text engine and does not provide speech
                synthesis.
        """
        raise VoiceProviderError(
            "FasterWhisperProvider does not support speech synthesis.",
            provider_name=self.name,
        )

    @staticmethod
    def _validate_constructor_args(model_name: str, device: str, compute_type: str) -> None:
        """Validates constructor arguments before they are stored.

        Args:
            model_name: Candidate Whisper model name or path.
            device: Candidate compute device.
            compute_type: Candidate CTranslate2 compute type.

        Raises:
            ValueError: If any argument is invalid.
        """
        if not model_name or not model_name.strip():
            raise ValueError("model_name must be a non-empty string.")
        if device not in _VALID_DEVICES:
            raise ValueError(f"device must be one of {sorted(_VALID_DEVICES)}, got {device!r}.")
        if not compute_type or not compute_type.strip():
            raise ValueError("compute_type must be a non-empty string.")

    def _get_model(self) -> WhisperModel:
        """Returns the loaded Whisper model, loading it if necessary.

        Uses the double-checked locking pattern so the model is loaded
        at most once, even under concurrent access.

        Returns:
            The loaded ``WhisperModel`` instance.

        Raises:
            VoiceInitializationError: If the model fails to load.
        """
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is None:
                try:
                    self._model = WhisperModel(
                        self._model_name,
                        device=self._device,
                        compute_type=self._compute_type,
                        download_root=self._download_root,
                    )
                except Exception as exc:
                    raise VoiceInitializationError(
                        "Failed to load the Faster-Whisper model.",
                        details={
                            "model_name": self._model_name,
                            "device": self._device,
                            "compute_type": self._compute_type,
                        },
                    ) from exc
        return self._model

    def _ensure_session_active(self, session_id: UUID) -> None:
        """Verifies that a session is registered on this provider.

        Args:
            session_id: Identifier of the session to check.

        Raises:
            VoiceSessionError: If the session is not registered.
        """
        with self._sessions_lock:
            if session_id not in self._active_session_ids:
                raise VoiceSessionError(
                    "Session is not active on this provider.",
                    session_id=str(session_id),
                )

    @staticmethod
    def _extract_audio_bytes(session: VoiceSession) -> bytes:
        """Extracts raw PCM WAV audio bytes from a session's metadata.

        Args:
            session: The voice session to extract audio from.

        Returns:
            The raw PCM WAV audio bytes associated with the session.

        Raises:
            SpeechRecognitionError: If no audio bytes are present or
                the stored value is not of type ``bytes``.
        """
        audio_bytes = session.metadata.get(_AUDIO_METADATA_KEY)
        if not isinstance(audio_bytes, bytes) or not audio_bytes:
            raise SpeechRecognitionError(
                "No audio bytes were found on the session to transcribe.",
                details={"session_id": str(session.session_id)},
            )
        return audio_bytes

    @staticmethod
    def _decode_wav_bytes(audio_bytes: bytes) -> np.ndarray:
        """Decodes raw PCM WAV bytes into a normalized float32 array.

        Args:
            audio_bytes: Raw WAV-encoded audio, expected to be
                single-channel, 16 kHz, 16-bit PCM.

        Returns:
            A one-dimensional ``numpy.ndarray`` of float32 samples in
            the range [-1.0, 1.0].

        Raises:
            SpeechRecognitionError: If the bytes are not a valid WAV
                file, or do not match the expected audio format.
        """
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                frame_rate = wav_file.getframerate()
                raw_frames = wav_file.readframes(wav_file.getnframes())
        except (wave.Error, EOFError) as exc:
            raise SpeechRecognitionError("Audio bytes are not a valid WAV file.") from exc

        if (
            channels != _EXPECTED_CHANNELS
            or sample_width != _EXPECTED_SAMPLE_WIDTH_BYTES
            or frame_rate != _EXPECTED_SAMPLE_RATE_HZ
        ):
            raise SpeechRecognitionError(
                "Audio does not match the required mono, 16 kHz, 16-bit PCM format.",
                details={
                    "channels": channels,
                    "sample_width_bytes": sample_width,
                    "frame_rate_hz": frame_rate,
                },
            )

        try:
            samples = np.frombuffer(raw_frames, dtype=np.int16).astype(np.float32)
        except ValueError as exc:
            raise SpeechRecognitionError("Failed to decode WAV audio samples.") from exc

        return samples / _PCM16_NORMALIZATION_FACTOR

    def _run_inference(
        self,
        samples: np.ndarray,
        session: VoiceSession,
    ) -> tuple[Iterator[Any], Any]:
        """Runs Whisper inference on decoded audio samples.

        Args:
            samples: Normalized float32 audio samples to transcribe.
            session: The voice session the audio belongs to, used to
                derive the language hint for transcription.

        Returns:
            A tuple of the segment iterator and transcription info
            object produced by the underlying model.

        Raises:
            SpeechRecognitionError: If inference fails.
            VoiceInitializationError: If the model fails to load.
        """
        model = self._get_model()
        language_hint = self._resolve_language_hint(session)
        with self._inference_lock:
            try:
                return model.transcribe(
                    samples,
                    language=language_hint,
                    beam_size=_DEFAULT_BEAM_SIZE,
                )
            except Exception as exc:
                raise SpeechRecognitionError(
                    "Faster-Whisper failed to transcribe the provided audio.",
                    details={"session_id": str(session.session_id)},
                ) from exc

    @staticmethod
    def _resolve_language_hint(session: VoiceSession) -> str | None:
        """Derives a Whisper language code hint from the session config.

        Returns ``None`` (auto-detect) whenever ``language_code`` is
        unset, empty, or the literal sentinel ``"auto"``. This is the
        default (``VoiceServiceConfig.language_code`` defaults to
        ``None``) so Hindi/Hinglish speech isn't force-fed an "en"
        hint on every call. Callers that want recognition pinned to a
        single language (e.g. because auto-detect is unreliable for
        their mic/accent) can still set an explicit BCP-47 code such
        as "en-US" or "hi-IN".

        KNOWN LIMITATION: Whisper (and faster-whisper) detects and
        transcribes at most one dominant language per utterance/
        segment — it does not do true intra-sentence code-switching.
        For a mixed Hinglish sentence, auto-detect will pick whichever
        language dominates that utterance and transcribe the whole
        segment as that language, occasionally transliterating the
        other language's words phonetically rather than switching
        scripts mid-sentence (e.g. "chrome open karo" said in one
        breath may come back fully in Devanagari, or fully in Latin
        script with "karo" spelled out phonetically, depending on
        which language the model judged dominant). This is a real
        constraint of the underlying model, not a bug in this glue
        code — don't claim seamless mid-sentence code-switching works.

        Args:
            session: The voice session to derive a language hint from.

        Returns:
            A bare Whisper language code (e.g. "en"), or ``None`` to
            request automatic language detection if no language is
            configured (the default) or "auto" was set explicitly.
        """
        language_code = session.config.language_code
        if not language_code or language_code.strip().lower() == "auto":
            return None
        return language_code.split("-")[0].lower()

    @staticmethod
    def _segment_confidence(segment: Any) -> float:
        """Converts a segment's average log-probability into a confidence.

        Args:
            segment: A single segment object produced by the Whisper
                model, exposing an ``avg_logprob`` attribute.

        Returns:
            An approximate confidence score in the range [0.0, 1.0].
        """
        return min(1.0, max(0.0, math.exp(segment.avg_logprob)))

    @classmethod
    def _average_confidence(cls, segments: list[Any]) -> float:
        """Averages the per-segment confidence across a full transcript.

        Args:
            segments: The list of segments produced for a transcript.

        Returns:
            The mean confidence across all segments, or ``0.0`` if no
            segments were produced.
        """
        if not segments:
            return 0.0
        # return sum(cls._segment_confidence(segment) for segment in segments) / len(segments)
        return (
            sum(cls._segment_confidence(segment) for segment in segments)
            / len(segments)
        )
