"""Piper backed text-to-speech provider for the EON Voice module.

This module provides ``PiperProvider``, a concrete implementation of
``TextToSpeechProvider`` backed by the Piper offline text-to-speech
engine.

Design notes:
    - ``PiperProvider`` is the only place in the Voice module that
      imports ``piper``. All other Voice components depend solely on
      the ``TextToSpeechProvider`` abstraction, keeping the concrete
      synthesis library isolated behind a single implementation
      (Dependency Inversion Principle). Replacing Piper with another
      TTS engine requires writing a new ``TextToSpeechProvider``
      implementation; no other code changes.
    - The underlying Piper voice model is loaded lazily, on first use,
      so constructing this provider is cheap and side-effect free.
      Model loading is guarded by a lock using the double-checked
      locking pattern to remain safe under concurrent access.
    - Synthesis calls are serialized behind a dedicated inference lock,
      since the underlying Piper voice instance is not guaranteed to be
      safe for concurrent invocation.
    - All exceptions raised by ``piper`` or the standard library's
      ``wave`` module are caught at the boundary of this class and
      translated into the project's own exception types
      (``VoiceInitializationError``, ``SpeechSynthesisError``,
      ``VoiceSessionError``, ``VoiceProviderError``); no third-party
      exception type ever escapes this module.
    - This provider performs speech synthesis only. Piper is a
      text-to-speech engine with no speech recognition capability, so
      ``transcribe`` and ``transcribe_stream`` always raise
      ``VoiceProviderError``.
    - Synthesized audio is never played back or written to disk by
      this provider. Generated WAV bytes are stored on
      ``session.metadata["audio_bytes"]``, with the ``VoiceSession``
      acting as the transport mechanism to downstream playback
      components.

Requires: Python 3.12+, piper-tts
"""

from __future__ import annotations

import io
import math
import threading
import wave
from collections.abc import Iterator
from uuid import UUID

from piper import PiperVoice

from src.core.logger import get_logger
from src.modules.voice.exceptions import (
    SpeechSynthesisError,
    VoiceInitializationError,
    VoiceProviderError,
    VoiceSessionError,
)
from src.modules.voice.models import (
    SpeechRecognitionResult,
    SpeechSynthesisRequest,
    VoiceSession,
)
from src.modules.voice.providers.tts import TextToSpeechProvider

from piper import PiperVoice
from piper.config import SynthesisConfig

_AUDIO_METADATA_KEY = "audio_bytes"
_HINDI_LANGUAGE_PREFIXES = ("hi",)  # matches "hi", "hi-IN", "hi_IN", etc.

logger = get_logger("PiperProvider")


class PiperProvider(TextToSpeechProvider):
    """Text-to-speech provider backed by the Piper offline TTS engine.

    ``PiperProvider`` synthesizes speech from a ``SpeechSynthesisRequest``
    using a locally loaded Piper voice model, writing the resulting raw
    WAV bytes onto the associated session's metadata. It performs no
    playback and no file I/O of its own; downstream components are
    responsible for consuming the generated audio. As a
    text-to-speech-only provider, it does not support speech
    recognition; ``transcribe`` and ``transcribe_stream`` always raise
    ``VoiceProviderError``.

    Attributes:
        _model_path: Filesystem path to the Piper voice model (``.onnx``
            file).
        _config_path: Filesystem path to the Piper voice model's JSON
            configuration file.
        _use_cuda: Whether the model should run on a CUDA-capable GPU.
        _speaker_id: Optional speaker identifier for multi-speaker
            voice models.
        _voice: The lazily loaded ``PiperVoice`` instance, or ``None``
            if not yet loaded.
        _load_lock: Guards lazy, thread-safe initialization of
            ``_voice``.
        _inference_lock: Serializes calls into the underlying voice
            model to avoid concurrent synthesis on a single instance.
        _active_session_ids: Identifiers of sessions currently started
            on this provider.
        _sessions_lock: Guards concurrent access to
            ``_active_session_ids``.
    """

    def __init__(
        self,
        model_path: str,
        config_path: str,
        use_cuda: bool = False,
        speaker_id: int | None = None,
        model_path_hi: str | None = None,
        config_path_hi: str | None = None,
    ) -> None:
        """Configures the provider without loading the voice model yet.

        Args:
            model_path: Filesystem path to the default Piper voice
                model (``.onnx`` file). Must be a non-empty string.
            config_path: Filesystem path to the default Piper voice
                model's JSON configuration file. Must be a non-empty
                string.
            use_cuda: Whether to run the model on a CUDA-capable GPU.
            speaker_id: Optional speaker identifier to select from a
                multi-speaker voice model. ``None`` uses the model's
                default speaker.
            model_path_hi: Optional filesystem path to a second,
                Hindi Piper voice model. When set (along with
                ``config_path_hi``), ``speak`` uses this voice for
                requests whose ``language_code`` indicates Hindi (e.g.
                "hi", "hi-IN"). Leave unset if no Hindi voice model is
                available — Piper will fall back to the default voice
                and log that Hindi TTS isn't configured. Hindi Piper
                voices can be downloaded from the rhasspy/piper-voices
                repository on Hugging Face
                (https://huggingface.co/rhasspy/piper-voices); this is
                an external asset the user fetches themselves, same as
                the default voice.
            config_path_hi: Optional filesystem path to the Hindi
                voice model's JSON configuration file. Required
                alongside ``model_path_hi`` for the Hindi voice to be
                usable.

        Raises:
            ValueError: If any argument fails validation.
        """
        self._validate_constructor_args(model_path, config_path, speaker_id)
        self._model_path = model_path
        self._config_path = config_path
        self._use_cuda = use_cuda
        self._speaker_id = speaker_id

        # Hindi voice is optional and validated the same way as the
        # default voice, but only when both paths are actually
        # provided — a partially configured Hindi voice (only one of
        # the two paths set) is treated as "not configured" rather
        # than raising, since this is commonly left unset entirely.
        self._model_path_hi = model_path_hi
        self._config_path_hi = config_path_hi
        self._hindi_voice_configured = bool(model_path_hi and config_path_hi)
        if self._hindi_voice_configured:
            self._validate_constructor_args(model_path_hi, config_path_hi, speaker_id)

        self._voice: PiperVoice | None = None
        self._voice_hi: PiperVoice | None = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

        self._active_session_ids: set[UUID] = set()
        self._sessions_lock = threading.Lock()

    @property
    def name(self) -> str:
        """Returns the unique, human-readable name of this provider.

        Returns:
            The literal string "piper".
        """
        return "piper"

    def initialize(self) -> None:
        """Eagerly loads the underlying Piper voice model.

        Calling this method is optional: the model is loaded lazily on
        first use regardless. Calling it explicitly allows
        initialization failures to surface before any session is
        created.

        Raises:
            VoiceInitializationError: If the voice model fails to load.
        """
        self._get_voice()

    def shutdown(self) -> None:
        """Releases the loaded Piper voice model and clears sessions.

        Sets the cached model reference to ``None`` and clears all
        active session registrations.
        """
        with self._load_lock:
            self._voice = None
            self._voice_hi = None
        with self._sessions_lock:
            self._active_session_ids.clear()

    def health_check(self) -> bool:
        """Reports whether the provider is loaded and ready for use.

        Returns:
            ``True`` if the Piper voice model has been successfully
            loaded, ``False`` otherwise.
        """
        return self._voice is not None

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

    def speak(
        self,
        session: VoiceSession,
        request: SpeechSynthesisRequest,
    ) -> None:
        """Synthesizes speech and stores the result on the session.

        Generated audio is written as raw WAV bytes to
        ``session.metadata["audio_bytes"]``. No audio is played back
        and no file is written to disk.

        Args:
            session: The voice session to synthesize speech for. Must
                be registered on this provider.
            request: The synthesis request describing the text and
                voice parameters to use.

        Raises:
            VoiceSessionError: If the session is not registered on this
                provider.
            SpeechSynthesisError: If synthesis fails.
            VoiceInitializationError: If the voice model fails to load.
        """
        self._ensure_session_active(session.session_id)
        session.metadata[_AUDIO_METADATA_KEY] = self._synthesize(request)

    def stop_speaking(self, session: VoiceSession) -> None:
        """Validates that a session may have its speech synthesis stopped.

        ``PiperProvider`` synthesizes audio synchronously and performs
        no playback of its own, so there is no in-progress operation to
        interrupt. This method exists to satisfy the
        ``TextToSpeechProvider`` contract and to surface a clear error
        if called against an unregistered session.

        Args:
            session: The voice session whose speech should be stopped.

        Raises:
            VoiceSessionError: If the session is not registered on this
                provider.
        """
        self._ensure_session_active(session.session_id)

    def is_speaking(self, session: VoiceSession) -> bool:
        """Reports whether speech synthesis is currently in progress.

        ``PiperProvider`` synthesizes audio synchronously within
        ``speak`` and returns only once synthesis is complete, so
        playback is never in progress by the time a caller can
        observe it. Always returns ``False`` once the session is
        confirmed active.

        Args:
            session: The voice session to check.

        Returns:
            Always ``False``.

        Raises:
            VoiceSessionError: If the session is not registered on this
                provider.
        """
        self._ensure_session_active(session.session_id)
        return False

    def transcribe(self, session: VoiceSession) -> SpeechRecognitionResult:
        """Always raises, since this provider does not support recognition.

        Args:
            session: Unused. Present to satisfy the ``VoiceProvider``
                interface.

        Raises:
            VoiceProviderError: Always. Piper is a text-to-speech
                engine and does not provide speech recognition.
        """
        raise VoiceProviderError(
            "PiperProvider does not support speech recognition.",
            provider_name=self.name,
        )

    def transcribe_stream(
        self,
        session: VoiceSession,
    ) -> Iterator[SpeechRecognitionResult]:
        """Always raises, since this provider does not support recognition.

        Args:
            session: Unused. Present for symmetry with speech-to-text
                provider implementations.

        Raises:
            VoiceProviderError: Always. Piper is a text-to-speech
                engine and does not provide speech recognition.
        """
        raise VoiceProviderError(
            "PiperProvider does not support speech recognition.",
            provider_name=self.name,
        )

    @staticmethod
    def _validate_constructor_args(
        model_path: str,
        config_path: str,
        speaker_id: int | None,
    ) -> None:
        """Validates constructor arguments before they are stored.

        Args:
            model_path: Candidate Piper model path.
            config_path: Candidate Piper model configuration path.
            speaker_id: Candidate speaker identifier.

        Raises:
            ValueError: If any argument is invalid.
        """
        if not model_path or not model_path.strip():
            raise ValueError("model_path must be a non-empty string.")
        if not config_path or not config_path.strip():
            raise ValueError("config_path must be a non-empty string.")
        if speaker_id is not None and speaker_id < 0:
            raise ValueError("speaker_id must be a non-negative integer or None.")

    def _get_voice(self) -> PiperVoice:
        """Returns the loaded default Piper voice, loading it if necessary.

        Uses the double-checked locking pattern so the voice model is
        loaded at most once, even under concurrent access.

        Returns:
            The loaded default ``PiperVoice`` instance.

        Raises:
            VoiceInitializationError: If the voice model fails to load.
        """
        if self._voice is not None:
            return self._voice
        with self._load_lock:
            if self._voice is None:
                try:
                    self._voice = PiperVoice.load(
                        self._model_path,
                        config_path=self._config_path,
                        use_cuda=self._use_cuda,
                    )
                except Exception as exc:
                    raise VoiceInitializationError(
                        "Failed to load the Piper voice model.",
                        details={
                            "model_path": self._model_path,
                            "config_path": self._config_path,
                            "use_cuda": self._use_cuda,
                        },
                    ) from exc
        return self._voice

    def _get_hindi_voice(self) -> PiperVoice | None:
        """Returns the loaded Hindi Piper voice, loading it if necessary.

        Returns ``None`` (rather than raising) when no Hindi voice was
        configured, so callers can treat "not configured" and "not yet
        loaded" uniformly and fall back to the default voice.

        Returns:
            The loaded Hindi ``PiperVoice`` instance, or ``None`` if
            ``model_path_hi``/``config_path_hi`` weren't provided.

        Raises:
            VoiceInitializationError: If a Hindi voice was configured
                but fails to load.
        """
        if not self._hindi_voice_configured:
            return None
        if self._voice_hi is not None:
            return self._voice_hi
        with self._load_lock:
            if self._voice_hi is None:
                try:
                    self._voice_hi = PiperVoice.load(
                        self._model_path_hi,
                        config_path=self._config_path_hi,
                        use_cuda=self._use_cuda,
                    )
                except Exception as exc:
                    raise VoiceInitializationError(
                        "Failed to load the Hindi Piper voice model.",
                        details={
                            "model_path": self._model_path_hi,
                            "config_path": self._config_path_hi,
                            "use_cuda": self._use_cuda,
                        },
                    ) from exc
        return self._voice_hi

    @staticmethod
    def _is_hindi_language_code(language_code: str | None) -> bool:
        """Reports whether a BCP-47 language code is Hindi-dominant.

        Args:
            language_code: A language code such as "hi", "hi-IN",
                "en-US", or ``None``.

        Returns:
            ``True`` if the code's primary subtag is "hi".
        """
        if not language_code:
            return False
        primary = language_code.strip().lower().split("-")[0].split("_")[0]
        return primary in _HINDI_LANGUAGE_PREFIXES

    def _select_voice(self, request: SpeechSynthesisRequest) -> PiperVoice:
        """Picks the default or Hindi voice for a synthesis request.

        Selection is based on ``request.language_code``, which
        reflects the *detected input language for that turn* (set by
        upstream callers from the STT result — see
        ``VoiceService.say``), not a fixed per-session setting: a
        Hindi-dominant turn gets the Hindi voice, everything else gets
        the default voice.

        IMPORTANT: this makes EON reply in either full Hindi or full
        English for a given turn, based on which language dominated
        the input. It does NOT synthesize genuinely mixed Hindi+English
        speech within a single sentence — a single Piper voice model
        isn't built for that. True intra-sentence Hinglish TTS would
        need a different TTS engine/voice entirely; that's a bigger,
        separate undertaking, not something this toggle provides.

        Args:
            request: The synthesis request to select a voice for.

        Returns:
            The Hindi voice if the request is Hindi-dominant and a
            Hindi voice is configured and loads successfully;
            otherwise the default voice.
        """
        if not self._is_hindi_language_code(request.language_code):
            return self._get_voice()

        if not self._hindi_voice_configured:
            logger.info(
                "Hindi TTS was requested but no Hindi Piper voice is "
                "configured (VoiceServiceConfig.piper_hi); falling "
                "back to the default voice."
            )
            return self._get_voice()

        try:
            return self._get_hindi_voice() or self._get_voice()
        except VoiceInitializationError:
            logger.warning(
                "Hindi Piper voice failed to load; falling back to "
                "the default voice.",
                exc_info=True,
            )
            return self._get_voice()

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

    def _synthesize(self, request: SpeechSynthesisRequest) -> bytes:
        """Synthesizes a request into raw WAV bytes using Piper.

        Args:
            request: The synthesis request describing the text and
                voice parameters to use.

        Returns:
            The synthesized audio, encoded as WAV bytes.

        Raises:
            SpeechSynthesisError: If the request text is empty or
                contains only whitespace, if ``speaking_rate`` is not a
                finite number, or if synthesis otherwise fails.
            VoiceInitializationError: If the voice model fails to load.
        """
        text = request.text
        self._validate_synthesis_text(text)
        length_scale = self._speaking_rate_to_length_scale(request.speaking_rate)
        # voice = self._get_voice()

        # synth_kwargs: dict[str, int | float] = {"length_scale": length_scale}
        # if self._speaker_id is not None:
        #     synth_kwargs["speaker_id"] = self._speaker_id

        # buffer = io.BytesIO()
        # with self._inference_lock:
        #     try:
        #         with wave.open(buffer, "wb") as wav_file:
        #             voice.synthesize(text, wav_file, **synth_kwargs)
        #     except Exception as exc:

        voice = self._select_voice(request)

        syn_config = SynthesisConfig(
            length_scale=length_scale,
            speaker_id=self._speaker_id,
        )

        buffer = io.BytesIO()
        with self._inference_lock:
            try:
                with wave.open(buffer, "wb") as wav_file:
                    voice.synthesize_wav(text, wav_file, syn_config=syn_config)
            except Exception as exc:

                raise SpeechSynthesisError(
                    "Piper failed to synthesize the requested text.",
                    details={"request_id": str(request.request_id)},
                ) from exc

        return buffer.getvalue()

    @staticmethod
    def _validate_synthesis_text(text: str) -> None:
        """Validates that synthesis request text is a non-empty string.

        Args:
            text: The text to validate.

        Raises:
            SpeechSynthesisError: If the text is not a string, or is
                empty or contains only whitespace.
        """
        if not isinstance(text, str) or not text.strip():
            raise SpeechSynthesisError("Speech synthesis text cannot be empty.")

    @staticmethod
    def _speaking_rate_to_length_scale(speaking_rate: float) -> float:
        """Converts a speaking rate multiplier into Piper's length scale.

        Piper's ``length_scale`` parameter is inversely proportional to
        speaking rate: values below ``1.0`` speed speech up, values
        above ``1.0`` slow it down.

        Args:
            speaking_rate: Relative speaking rate, where ``1.0`` is
                normal speed.

        Returns:
            The corresponding Piper ``length_scale`` value.

        Raises:
            SpeechSynthesisError: If ``speaking_rate`` is not a finite
                number (e.g. ``NaN`` or infinite), or is not greater
                than zero.
        """
        if not math.isfinite(speaking_rate):
            raise SpeechSynthesisError(
                "speaking_rate must be a finite number.",
                details={"speaking_rate": speaking_rate},
            )
        if speaking_rate <= 0:
            raise SpeechSynthesisError(
                "speaking_rate must be greater than zero.",
                details={"speaking_rate": speaking_rate},
            )
        return 1.0 / speaking_rate
