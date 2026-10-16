"""Wake-word listener for the EON Voice module.

Design notes:
    - There is no pretrained neural wake-word model for an arbitrary
      custom word like "EON": offline wake-word engines (openWakeWord,
      Porcupine, etc.) ship models for a fixed set of phrases (e.g.
      "hey jarvis", "alexa"), and training a bespoke one is a separate,
      much heavier effort. ``WakeWordListener`` instead reuses the STT
      provider that is already loaded for normal listening, running it
      on short rolling audio windows. This adds no new dependency and
      keeps the wake word user-configurable via plain text.
    - A cheap RMS energy check (a minimal voice-activity gate) is used
      to skip transcribing near-silent windows, since continuous
      transcription would otherwise burn CPU checking audio that
      obviously contains no speech.
    - Runs entirely on a dedicated daemon thread. It must never be
      driven from the main thread, since it blocks on microphone reads
      in a loop for as long as it is running.
    - Microphone access is serialized via a caller-supplied lock, since
      a single physical microphone cannot be started/stopped by two
      independent readers (e.g. this listener and a manual
      ``VoiceService.listen_once`` call) at the same time.
    - Detection reuses the caller's existing ``VoiceSession`` (via
      ``VoiceManager.transcribe``) rather than creating a second,
      parallel session, so it shares the same STT provider session
      state as normal listening.

Requires: Python 3.12+
"""

from __future__ import annotations

import array
import io
import re
import threading
import wave
from collections.abc import Callable

from src.core.logger import get_logger
from src.modules.voice.exceptions import VoiceError
from src.modules.voice.manager import VoiceManager
from src.modules.voice.microphone import Microphone
from src.modules.voice.speaker_id import SpeakerIdentifier

logger = get_logger("WakeWord")

_BYTES_PER_SAMPLE = 2  # 16-bit mono PCM


def _levenshtein(a: str, b: str) -> int:
    """Computes the Levenshtein (edit) distance between two strings.

    Standalone, dependency-free implementation (no third-party fuzzy
    matching library needed for what is otherwise a single small
    utility function).

    Args:
        a: First string.
        b: Second string.

    Returns:
        The minimum number of single-character insertions, deletions,
        or substitutions needed to turn ``a`` into ``b``.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current_row = [i]
        for j, char_b in enumerate(b, start=1):
            insert_cost = current_row[j - 1] + 1
            delete_cost = previous_row[j] + 1
            replace_cost = previous_row[j - 1] + (char_a != char_b)
            current_row.append(min(insert_cost, delete_cost, replace_cost))
        previous_row = current_row

    return previous_row[-1]


class WakeWordListener:
    """Continuously listens for a configured wake word in the background.

    Attributes:
        _microphone: Shared microphone device to capture audio from.
        _manager: Voice manager used to run transcription for the
            reused session.
        _mic_lock: Lock serializing microphone start/stop/read calls
            against other consumers of the same microphone.
        _wake_pattern: Compiled, whole-word, case-insensitive pattern
            matching the configured wake word within a transcript.
        _sample_rate_hz: Sample rate, in hertz, audio is captured at.
        _window_seconds: Duration of each rolling audio window checked
            for the wake word.
        _check_interval_seconds: Minimum pause between the end of one
            check and the start of the next.
        _energy_threshold: Minimum RMS energy a window must have before
            it is transcribed at all.
        _on_wake: Callback invoked (on this listener's background
            thread) whenever the wake word is heard.
    """

    def __init__(
        self,
        microphone: Microphone,
        manager: VoiceManager,
        mic_lock: threading.Lock,
        wake_word: str,
        sample_rate_hz: int,
        window_seconds: float,
        check_interval_seconds: float,
        energy_threshold: float,
        on_wake: Callable[[bool], None],
        speaker_identifier: SpeakerIdentifier | None = None,
    ) -> None:
        if not wake_word or not wake_word.strip():
            raise ValueError("wake_word must be a non-empty string.")

        self._microphone = microphone
        self._manager = manager
        self._mic_lock = mic_lock
        self._wake_word = wake_word.strip().lower()
        self._wake_pattern = re.compile(
            r"\b" + re.escape(self._wake_word) + r"\b"
        )
        self._sample_rate_hz = sample_rate_hz
        self._window_seconds = window_seconds
        self._check_interval_seconds = check_interval_seconds
        self._energy_threshold = energy_threshold
        self._on_wake = on_wake
        self._speaker_identifier = speaker_identifier

        self._session_id_provider: Callable[[], object] | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def is_running(self) -> bool:
        """Whether the background listening thread is currently active."""
        return self._thread is not None and self._thread.is_alive()

    def start(self, session_id_provider: Callable[[], object]) -> None:
        """Starts the background wake-word listening thread.

        Args:
            session_id_provider: Zero-argument callable returning the
                session id to transcribe against. Called on every
                check, so it can reflect a session created after this
                listener was constructed.

        Does nothing if the listener is already running.
        """
        if self.is_running:
            return

        self._session_id_provider = session_id_provider
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="EON-WakeWord",
            daemon=True,
        )
        self._thread.start()
        logger.info("Wake word listener started (wake word: '%s').", self._wake_word)

    def stop(self) -> None:
        """Stops the background wake-word listening thread.

        Blocks briefly for the thread to exit cleanly. Safe to call
        even if the listener is not currently running.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        logger.info("Wake word listener stopped.")

    def _run(self) -> None:
        """Main loop for the background listening thread."""
        while not self._stop_event.is_set():
            try:
                audio = self._capture_window()
                if audio is not None and self._rms(audio) >= self._energy_threshold:
                    if self._heard_wake_word(audio):
                        is_owner = self._verify_owner(audio)
                        logger.info(
                            "Wake word detected (owner recognized: %s).", is_owner
                        )
                        # Run the callback on its own thread instead of
                        # inline: on_wake() typically listens, thinks,
                        # and speaks, which can take several seconds.
                        # Running it inline would block this loop for
                        # that whole time, so a second "EON" said while
                        # EON is still speaking (a barge-in) would never
                        # be heard. A dedicated thread keeps this loop
                        # free to keep listening throughout.
                        threading.Thread(
                            target=self._safe_on_wake,
                            args=(is_owner,),
                            name="EON-WakeWord-Callback",
                            daemon=True,
                        ).start()
            except Exception:
                # A single failed cycle (e.g. a transient microphone
                # hiccup) must never kill the background thread.
                logger.exception("Error during wake word check cycle.")

            self._stop_event.wait(self._check_interval_seconds)

    def _verify_owner(self, pcm_bytes: bytes) -> bool:
        """Checks whether the same audio that triggered the wake word
        also sounds like the enrolled owner.

        Reuses the exact audio window already captured for wake-word
        detection — no second recording is made. Returns ``False`` (no
        exception) if nothing is enrolled or verification itself fails
        for any reason, since this only ever gates a personalized
        greeting, never whether EON responds at all.
        """
        if self._speaker_identifier is None or not self._speaker_identifier.is_enrolled:
            return False

        try:
            return self._speaker_identifier.verify(pcm_bytes, self._sample_rate_hz)
        except Exception:
            logger.exception("Speaker verification failed; treating as unrecognized.")
            return False

    def _safe_on_wake(self, is_owner: bool) -> None:
        """Runs the configured ``on_wake`` callback, isolating errors.

        Runs on its own short-lived thread (see ``_run``), so an
        exception here would otherwise be silently swallowed by the
        default thread excepthook without ever reaching the listener
        loop's own try/except. Logging it here keeps behavior identical
        to the previous inline-call version.
        """
        try:
            self._on_wake(is_owner)
        except Exception:
            logger.exception("Wake word callback raised an exception.")

    def _capture_window(self) -> bytes | None:
        """Records one rolling window of audio from the microphone.

        Returns:
            The captured PCM audio, or ``None`` if the microphone
            isn't open or capture was interrupted by a stop request.
        """
        target_bytes = int(
            self._sample_rate_hz * _BYTES_PER_SAMPLE * self._window_seconds
        )
        frames: list[bytes] = []
        collected = 0

        with self._mic_lock:
            if not self._microphone.is_open or self._stop_event.is_set():
                return None
            try:
                self._microphone.start_recording()
            except VoiceError:
                return None
            try:
                while collected < target_bytes and not self._stop_event.is_set():
                    try:
                        frame = self._microphone.read_frame()
                    except VoiceError:
                        break
                    frames.append(frame)
                    collected += len(frame)
            finally:
                try:
                    self._microphone.stop_recording()
                except VoiceError:
                    pass

        return b"".join(frames) if frames else None

    def _heard_wake_word(self, pcm_bytes: bytes) -> bool:
        """Transcribes ``pcm_bytes`` and checks it for the wake word."""
        if self._session_id_provider is None:
            return False

        session_id = self._session_id_provider()
        if session_id is None:
            return False

        try:
            session = self._manager.get_session(session_id)  # type: ignore[arg-type]
            session.metadata["audio_bytes"] = self._wrap_pcm_as_wav(pcm_bytes)
            result = self._manager.transcribe(session_id)  # type: ignore[arg-type]
        except VoiceError:
            return False

        transcript = (result.transcript or "").strip().lower()
        if not transcript:
            return False

        # Logged at INFO (not DEBUG) deliberately: seeing exactly what
        # the STT model heard is the single most useful signal for
        # tuning the wake word or the energy threshold, and there is
        # no other visibility into these background checks otherwise.
        logger.info("Wake word check heard: '%s'", transcript)

        if self._wake_pattern.search(transcript):
            return True

        return self._fuzzy_wake_word_match(transcript)

    def _fuzzy_wake_word_match(self, transcript: str) -> bool:
        """Tolerates the STT model slightly mishearing the wake word.

        Short, unusual words (like most custom wake words) are prone
        to being misheard by speech-to-text models, especially on
        short audio clips (e.g. "eon" transcribed as "on" or "ian").
        Each word-like token in the transcript is compared against the
        wake word using edit distance, so close mishearings still
        count as a match while unrelated words do not.

        Args:
            transcript: The lowercased transcript to check.

        Returns:
            ``True`` if any token in the transcript is within a small
            edit distance of the configured wake word.
        """
        max_distance = 1 if len(self._wake_word) <= 4 else 2

        for token in re.findall(r"[a-z']+", transcript):
            if abs(len(token) - len(self._wake_word)) > max_distance:
                continue
            if _levenshtein(token, self._wake_word) <= max_distance:
                return True

        return False

    def _wrap_pcm_as_wav(self, pcm_bytes: bytes) -> bytes:
        """Wraps raw 16-bit mono PCM bytes in an in-memory WAV container."""
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(_BYTES_PER_SAMPLE)
            wav_file.setframerate(self._sample_rate_hz)
            wav_file.writeframes(pcm_bytes)
        return buffer.getvalue()

    @staticmethod
    def _rms(pcm_bytes: bytes) -> float:
        """Computes the root-mean-square energy of 16-bit mono PCM audio."""
        usable_length = len(pcm_bytes) - (len(pcm_bytes) % _BYTES_PER_SAMPLE)
        if usable_length <= 0:
            return 0.0

        samples = array.array("h")
        samples.frombytes(pcm_bytes[:usable_length])
        if not samples:
            return 0.0

        sum_squares = sum(sample * sample for sample in samples)
        return (sum_squares / len(samples)) ** 0.5
