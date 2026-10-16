"""
Voice Service.

Public interface for interacting with EON's Voice subsystem.

Mirrors the shape of ``MemoryService``: a single, high-level entry
point that the rest of the application depends on, hiding the
``VoiceManager``/provider/session wiring behind a small surface.
"""

from __future__ import annotations

import io
import wave
from uuid import UUID

from src.core.logger import get_logger
from src.modules.voice.config import VoiceServiceConfig
from src.modules.voice.exceptions import VoiceError
from src.modules.voice.manager import VoiceManager
from src.modules.voice.microphone import Microphone
from src.modules.voice.models import (
    SpeechRecognitionResult,
    SpeechSynthesisRequest,
    VoiceConfig,
    VoiceProviderType,
    VoiceSession,
)
from src.modules.voice.speaker import Speaker
from src.modules.voice.speaker_id import SpeakerIdentifier

import threading
from collections.abc import Callable

from src.modules.voice.bargein import BargeInListener
from src.modules.voice.conversation import is_exit_phrase
from src.modules.voice.endpointing import EndpointDecision, UtteranceEndpoint
from src.modules.voice.wakeword import WakeWordListener
from src.utils.audio import pcm_frame_seconds, rms_pcm

logger = get_logger("VoiceService")

_PROVIDER_TYPE_BY_NAME = {
    "faster_whisper": VoiceProviderType.FASTER_WHISPER,
    "piper": VoiceProviderType.PIPER,
    "openai": VoiceProviderType.OPENAI,
}


class VoiceService:
    """
    High-level interface for the Voice subsystem.

    This class is the single entry point the rest of EON should use
    for speech capabilities: starting/stopping voice sessions,
    listening for an utterance, and speaking text back to the user.
    It owns the ``VoiceManager`` (session + provider coordination) and
    the ``Microphone``/``Speaker`` device abstractions, but contains no
    provider-specific or audio-backend-specific logic of its own.
    """

    def __init__(
        self,
        manager: VoiceManager,
        microphone: Microphone,
        speaker: Speaker,
        config: VoiceServiceConfig,
    ) -> None:
        self._manager = manager
        self._microphone = microphone
        self._speaker = speaker
        self._config = config
        self._default_session_id: UUID | None = None

        # Guards microphone start/stop/read calls so manual listening
        # (listen_once) and the background wake-word listener never try
        # to drive the same physical microphone at the same time.
        self._mic_lock = threading.Lock()
        self._wake_word_listener: WakeWordListener | None = None
        self._barge_in_listener: BargeInListener | None = None
        self._in_conversation = False

        self._speaker_identifier = SpeakerIdentifier(
            profile_path=config.speaker_profile_path,
            threshold=config.speaker_verification_threshold,
        )

        # Barge-in: set by interrupt_speaking() while a say() call's
        # playback is in progress, so say() can tell an intentional
        # interruption apart from a genuine playback failure.
        self._interrupted = threading.Event()

        logger.info("Voice Service initialized.")

    def initialize(self) -> None:
        """
        Initialize the voice providers and open the audio devices.
        """
        self._manager.initialize()
        self._microphone.open()
        self._speaker.open()

    def shutdown(self) -> None:
        """
        Shutdown the voice providers and close the audio devices.
        """
        self.stop_wake_word_listening()

        if self._microphone.is_open:
            self._microphone.close()

        if self._speaker.is_open:
            self._speaker.close()

        self._manager.shutdown()

    def health_check(self) -> bool:
        """
        Return whether the underlying voice providers are healthy.
        """
        return self._manager.health_check()

    def start_session(self, user_id: str | None = None) -> VoiceSession:
        """
        Start a new voice session using the configured default provider.
        """
        provider_type = _PROVIDER_TYPE_BY_NAME.get(
            self._config.stt_provider,
            VoiceProviderType.CUSTOM,
        )

        config = VoiceConfig(
            provider_type=provider_type,
            language_code=self._config.language_code,
            sample_rate_hz=self._config.sample_rate_hz,
        )

        session = self._manager.create_session(config)
        session.user_id = user_id
        self._default_session_id = session.session_id

        return session

    @property
    def default_session_id(self) -> UUID | None:
        """
        The session id from the most recent ``start_session`` call that
        hasn't been stopped yet, or ``None`` if there isn't one.

        Lets other modules (e.g. Proactive Speech) speak through the
        same session the console/wake-word loop already opened,
        without needing their own session-tracking logic.
        """
        return self._default_session_id

    def stop_session(self, session_id: UUID) -> None:
        """
        Stop a voice session.
        """
        self._manager.stop_session(session_id)
        if self._default_session_id == session_id:
            self._default_session_id = None

    def listen_once(
        self,
        session_id: UUID,
        seconds: float | None = None,
    ) -> SpeechRecognitionResult:
        """
        Record a single utterance from the microphone and transcribe it.

        Args:
            session_id: The active session to transcribe audio for.
            seconds: How long to record for. Defaults to
                ``VoiceServiceConfig.listen_seconds``.

        Returns:
            The speech recognition result for the recorded audio.
        """
        duration = seconds if seconds is not None else self._config.listen_seconds

        session = self._manager.get_session(session_id)

        # The microphone is single-reader and the wake-word listener cycles
        # it every couple of seconds, so pause it for the duration — the
        # same thing ``listen_until_silence`` already does. In conversation
        # mode it is already paused, so leave it alone and don't un-pause it
        # when we finish.
        paused_here = False
        if not self._in_conversation:
            self._pause_wake_word_listening()
            paused_here = True

        try:
            audio_bytes = self._record_wav(duration)
        finally:
            if paused_here:
                self._resume_wake_word_listening()

        session.metadata["audio_bytes"] = audio_bytes

        return self._manager.transcribe(session_id)

    def listen_until_silence(
        self,
        session_id: UUID,
        *,
        wait_for_speech_seconds: float | None = None,
        silence_end_seconds: float | None = None,
        max_seconds: float | None = None,
        min_speech_seconds: float | None = None,
    ) -> SpeechRecognitionResult | None:
        """Records until the speaker stops talking, then transcribes it.

        Unlike ``listen_oncef� (a fixed-duration recording), this stops
        as soon as the speaker has been quiet for ``silence_end_seconds``
        — so a short answer returns quickly and a long question isn't
        cut off mid-sentence.

        Args:
            session_id: The active session to transcribe audio for.
            wait_for_speech_seconds: How long to wait for speech to
                begin. Defaults to ``listen_start_timeout_seconds``.
            silence_end_seconds: Silence that ends the utterance.
                Defaults to ``silence_end_seconds`` on the config.
            max_seconds: Hard recording cap. Defaults to
                ``listen_max_seconds``.
            min_speech_seconds: Least speech needed to count. Defaults
                to ``listen_min_speech_seconds``.

        Returns:
            The recognition result, or ``None`` if no usable speech was
            captured.
        """
        pcm_bytes = self._record_utterance(
            wait_for_speech_seconds=(
                wait_for_speech_seconds
                if wait_for_speech_seconds is not None
                else self._config.listen_start_timeout_seconds
            ),
            silence_end_seconds=(
                silence_end_seconds
                if silence_end_seconds is not None
                else self._config.silence_end_seconds
            ),
            max_seconds=(
                max_seconds
                if max_seconds is not None
                else self._config.listen_max_seconds
            ),
            min_speech_seconds=(
                min_speech_seconds
                if min_speech_seconds is not None
                else self._config.listen_min_speech_seconds
            ),
        )

        if pcm_bytes is None:
            return None

        session = self._manager.get_session(session_id)
        session.metadata["audio_bytes"] = self._wrap_pcm_as_wav(pcm_bytes)

        return self._manager.transcribe(session_id)

    def _record_utterance(
        self,
        *,
        wait_for_speech_seconds: float,
        silence_end_seconds: float,
        max_seconds: float,
        min_speech_seconds: float,
    ) -> bytes | None:
        """Records one endpointed utterance of raw PCM, or ``None``.

        Drives ``UtteranceEndpoint`` from per-frame energy and stops as
        soon as it says to — the speaker went quiet, the hard cap was
        reached, or nothing was ever said.
        """
        endpoint = UtteranceEndpoint(
            silence_end_seconds=silence_end_seconds,
            max_seconds=max_seconds,
            min_speech_seconds=min_speech_seconds,
            start_timeout_seconds=wait_for_speech_seconds,
        )

        sample_rate_hz = self._config.sample_rate_hz
        energy_threshold = self._config.wake_word_energy_threshold
        frames: list[bytes] = []
        decision = EndpointDecision.CONTINUE

        with self._mic_lock:
            self._microphone.start_recording()
            try:
                while decision is EndpointDecision.CONTINUE:
                    try:
                        frame = self._microphone.read_frame()
                    except VoiceError:
                        break

                    frames.append(frame)
                    decision = endpoint.update(
                        pcm_frame_seconds(len(frame), sample_rate_hz),
                        rms_pcm(frame) >= energy_threshold,
                    )
            finally:
                self._microphone.stop_recording()

        if decision is EndpointDecision.STOP_NO_SPEECH or not frames:
            return None

        return b"".join(frames)

    def run_conversation(
        self,
        session_id: UUID,
        on_utterance: Callable[[str, str | None], None],
        *,
        idle_timeout_seconds: float | None = None,
    ) -> int:
        """Holds a hands-free conversation until the user stops talking.

        After the wake word, this keeps listening for follow-up turns
        and calls ``on_utterance(text, language_code)`` for each, so the
        user does not have to say the wake word again between turns. The
        conversation ends when the user is silent for
        ``idle_timeout_seconds`` (default
        ``conversation_idle_timeout_seconds``), says an exit phrase, or
        nothing was heard at all.

        The wake-word listener is paused for the duration, so EON never
        transcribes its own replies or the follow-up turns through the
        wake-word path; it is resumed when the conversation ends.

        Args:
            session_id: The active session to listen/transcribe on.
            on_utterance: Called with ``(transcript, language_code)``
                for each accepted turn. It is expected to produce EON's
                reply (typically by speaking it) before returning.
            idle_timeout_seconds: Overrides the configured idle timeout.

        Returns:
            How many turns were handled.
        """
        idle_timeout = (
            idle_timeout_seconds
            if idle_timeout_seconds is not None
            else self._config.conversation_idle_timeout_seconds
        )
        single_turn = not self._config.conversation_mode_enabled
        wait_for_speech = (
            self._config.listen_start_timeout_seconds if single_turn else idle_timeout
        )

        self._pause_wake_word_listening()
        self._in_conversation = True
        turns = 0

        try:
            while True:
                result = self.listen_until_silence(
                    session_id,
                    wait_for_speech_seconds=wait_for_speech,
                )

                if result is None:
                    logger.info(
                        "Conversation ended: no speech within %.1fs.",
                        wait_for_speech,
                    )
                    break

                text = (result.transcript or "").strip()
                if not text:
                    logger.info("Conversation ended: empty transcript.")
                    break

                if is_exit_phrase(text, self._config.conversation_exit_phrases):
                    logger.info("Conversation ended: exit phrase %r.", text)
                    break

                turns += 1
                on_utterance(text, result.language_code)

                if single_turn:
                    break
        finally:
            self._in_conversation = False
            self._resume_wake_word_listening()

        return turns

    def _pause_wake_word_listening(self) -> None:
        """Suspends the wake-word listener, if one exists."""
        if self._wake_word_listener is not None:
            self._wake_word_listener.pause()

    def _resume_wake_word_listening(self) -> None:
        """Resumes the wake-word listener if it is still running."""
        if (
            self._wake_word_listener is not None
            and self._wake_word_listener.is_running
        ):
            self._wake_word_listener.resume()

    def _begin_barge_in(self) -> BargeInListener | None:
        """Starts listening for a spoken interruption during playback.

        Returns the listener so the caller can stop it afterwards, or
        ``None`` when barge-in is disabled or one is already running.
        """
        if not self._config.barge_in_enabled or self._barge_in_listener is not None:
            return None

        listener = BargeInListener(
            microphone=self._microphone,
            mic_lock=self._mic_lock,
            sample_rate_hz=self._config.sample_rate_hz,
            window_seconds=self._config.bargein_window_seconds,
            energy_threshold=self._config.bargein_energy_threshold,
            min_speech_seconds=self._config.bargein_min_speech_seconds,
            on_barge_in=self.interrupt_speaking,
        )

        # The microphone is single-reader: pause the wake-word listener
        # for the duration so only the barge-in listener is capturing.
        # In conversation mode it is already paused, so leave it alone
        # and don't un-pause it when we finish.
        if not self._in_conversation:
            self._pause_wake_word_listening()

        listener.start()
        self._barge_in_listener = listener
        return listener

    def _end_barge_in(self, listener: BargeInListener | None) -> None:
        """Stops the barge-in listener started by :meth:`_begin_barge_in`."""
        if listener is None:
            return

        listener.stop()
        self._barge_in_listener = None

        if not self._in_conversation:
            self._resume_wake_word_listening()

    @property
    def is_speaking(self) -> bool:
        """
        Whether EON is currently outputting speech through the speaker.

        Backed by the physical speaker's own state rather than session
        state, since ``VoiceManager.speak`` only covers synthesis (fast,
        not the blocking part); the actual device playback that this
        needs to reflect happens afterwards, in ``say``.
        """
        return self._speaker.is_playing

    def was_interrupted(self) -> bool:
        """
        Whether the most recently completed ``say`` call was cut short
        by ``interrupt_speaking``, rather than finishing on its own.

        Not cleared by this call — ``say`` clears the underlying flag
        itself at the start of its *next* call. Meant for callers that
        speak several chunks back-to-back (e.g. a streamed reply,
        sentence by sentence) and need to stop feeding further chunks
        the moment one gets interrupted, instead of speaking the rest
        of the reply right after a deliberate barge-in.
        """
        return self._interrupted.is_set()

    def interrupt_speaking(self) -> bool:
        """
        Immediately stops any speech currently playing (barge-in).

        Safe to call from any thread, including while another thread is
        blocked inside ``say``. Does nothing if EON isn't speaking.

        Returns:
            ``True`` if playback was actually interrupted, ``False`` if
            EON wasn't speaking.
        """
        if not self._speaker.is_playing:
            return False

        self._interrupted.set()

        try:
            self._speaker.stop()
        except VoiceError as exc:
            logger.warning("Failed to stop speaker playback cleanly: %s", exc)

        logger.info("Speech interrupted (barge-in).")
        return True

    def say(
        self,
        session_id: UUID,
        text: str,
        voice_id: str | None = None,
        language_code: str | None = None,
    ) -> None:
        """
        Synthesize ``text`` and play it back through the speaker.

        If ``interrupt_speaking`` is called on another thread while
        playback is in progress, this returns early and quietly instead
        of raising, since a barge-in is an expected user action, not a
        failure.

        Args:
            session_id: The active session to synthesize speech for.
            text: The text to speak.
            voice_id: Optional voice override for this request.
            language_code: Optional per-turn language override (e.g.
                the ``language_code`` Whisper detected for the user's
                last utterance, from the ``SpeechRecognitionResult``
                returned by ``listen_once``/``transcribe``). Lets a
                Hindi-dominant turn get a Hindi reply even though
                ``VoiceServiceConfig.language_code`` itself is a
                fixed, session-level default (typically ``None`` for
                auto-detect and not meaningful as a synthesis
                language). Falls back to that config default if not
                given.
        """
        request = SpeechSynthesisRequest(
            session_id=session_id,
            text=text,
            voice_id=voice_id if voice_id is not None else self._config.voice_id,
            language_code=(
                language_code
                if language_code is not None
                else self._config.language_code
            ),
            speaking_rate=self._config.speaking_rate,
        )

        self._manager.speak(session_id, request)

        session = self._manager.get_session(session_id)
        audio_bytes = session.metadata.get("audio_bytes")

        if not audio_bytes:
            return

        self._interrupted.clear()

        barge_in = self._begin_barge_in()
        try:
            self._speaker.play(self._decode_wav_to_pcm(audio_bytes))
        except VoiceError:
            if self._interrupted.is_set():
                # Playback failed because interrupt_speaking() aborted
                # the stream on purpose; this is not an error.
                return
            raise
        finally:
            self._end_barge_in(barge_in)

    # def _record_wav(self, seconds: float) -> bytes:
    #     """
    #     Capture ``seconds`` of audio from the microphone as WAV bytes.
    #     """
    #     frame_count = 0
    #     frames: list[bytes] = []

    #     self._microphone.start_recording()

    #     try:
    #         while True:
    #             frame = self._microphone.read_frame()
    #             frames.append(frame)
    #             frame_count += len(frame)

    #             approx_bytes_needed = int(
    #                 seconds * self._config.sample_rate_hz * 2  # 16-bit mono
    #             )

    #             if frame_count >= approx_bytes_needed:
    #                 break
    #     except VoiceError:
    #         raise
    #     finally:
    #         self._microphone.stop_recording()

    #     return self._wrap_pcm_as_wav(b"".join(frames))

    def start_wake_word_listening(self, on_detected: Callable[[bool], None]) -> None:
        """Starts listening in the background for the configured wake word.

        Args:
            on_detected: Called with one argument, ``is_owner``, each
                time the wake word is heard — ``True`` if the audio
                also matched the enrolled owner's voiceprint (see
                ``enroll_speaker``), ``False`` otherwise (including
                when nothing has been enrolled yet). EON still
                responds either way; this only distinguishes whether
                to greet the enrolled owner specifically.
        """
        if not self._config.wake_word_enabled:
            logger.info("Wake word listening is disabled in config; not starting.")
            return

        if self._wake_word_listener is None:
            self._wake_word_listener = WakeWordListener(
                microphone=self._microphone,
                manager=self._manager,
                mic_lock=self._mic_lock,
                wake_word=self._config.wake_word,
                sample_rate_hz=self._config.sample_rate_hz,
                window_seconds=self._config.wake_word_window_seconds,
                check_interval_seconds=self._config.wake_word_check_interval_seconds,
                energy_threshold=self._config.wake_word_energy_threshold,
                on_wake=on_detected,
                speaker_identifier=(
                    self._speaker_identifier
                    if self._config.speaker_verification_enabled
                    else None
                ),
            )

        self._wake_word_listener.start(
            session_id_provider=lambda: self._default_session_id
        )

    def stop_wake_word_listening(self) -> None:
        """Stops the background wake-word listener, if it is running."""
        if self._wake_word_listener is not None:
            self._wake_word_listener.stop()

    @property
    def is_speaker_enrolled(self) -> bool:
        """Whether an owner voiceprint has been enrolled (see ``enroll_speaker``)."""
        return self._speaker_identifier.is_enrolled

    @property
    def speaker_enroll_seconds(self) -> float:
        """Default recording duration used by ``enroll_speaker``."""
        return self._config.speaker_enroll_seconds

    def enroll_speaker(self, seconds: float | None = None) -> None:
        """Records a sample of speech and enrolls it as the owner's voice.

        Blocks for the recording duration. Overwrites any previously
        enrolled profile — only one owner is supported. See
        ``SpeakerIdentifier`` for what this is (and isn't): a
        lightweight spectral/pitch fingerprint, not a strong biometric
        security boundary.

        Args:
            seconds: How long to record for. Defaults to
                ``VoiceServiceConfig.speaker_enroll_seconds``.

        Raises:
            ValueError: If the recorded audio has no usable voiced
                content (e.g. silence) to enroll from.
        """
        duration = seconds if seconds is not None else self._config.speaker_enroll_seconds
        pcm_bytes = self._record_pcm(duration)
        self._speaker_identifier.enroll(pcm_bytes, self._config.sample_rate_hz)

    def _record_pcm(self, seconds: float) -> bytes:
        """Records raw microphone audio without WAV-wrapping it.

        Shared by ``_record_wav`` (which wraps this for STT) and
        ``enroll_speaker`` (which needs raw PCM directly, not a WAV
        container).
        """
        frame_count = 0
        frames: list[bytes] = []

        with self._mic_lock:
            self._microphone.start_recording()
            try:
                while True:
                    frame = self._microphone.read_frame()
                    frames.append(frame)
                    frame_count += len(frame)
                    approx_bytes_needed = int(seconds * self._config.sample_rate_hz * 2)
                    if frame_count >= approx_bytes_needed:
                        break
            except VoiceError:
                raise
            finally:
                self._microphone.stop_recording()

        return b"".join(frames)

    def _record_wav(self, seconds: float) -> bytes:
        return self._wrap_pcm_as_wav(self._record_pcm(seconds))

    def _wrap_pcm_as_wav(self, pcm_bytes: bytes) -> bytes:
        """
        Wrap raw 16-bit mono PCM bytes in a WAV container, in memory.
        """
        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self._config.sample_rate_hz)
            wav_file.writeframes(pcm_bytes)

        return buffer.getvalue()

    def _decode_wav_to_pcm(self, wav_bytes: bytes) -> bytes:
        """
        Extract raw PCM frames from a WAV container.
        """
        buffer = io.BytesIO(wav_bytes)

        with wave.open(buffer, "rb") as wav_file:
            return wav_file.readframes(wav_file.getnframes())
