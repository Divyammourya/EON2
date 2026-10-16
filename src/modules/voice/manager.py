"""Central coordinator for the EON Voice module.

This module defines ``VoiceManager``, the top-level coordination point
for the Voice module. ``VoiceManager`` orchestrates session lifecycle,
speech recognition, and speech synthesis by delegating to injected,
abstract collaborators: a ``VoiceSessionManager`` and provider
implementations of ``SpeechToTextProvider`` and ``TextToSpeechProvider``.

Design notes:
    - ``VoiceManager`` depends only on abstractions (``VoiceProvider``
      subclasses and ``VoiceSessionManager``), never on concrete
      provider implementations such as Faster-Whisper, Piper, OpenAI,
      or Ollama, and never on microphone or speaker implementations
      (Dependency Inversion Principle).
    - All collaborators are supplied via constructor injection, so the
      manager can be composed with any conforming provider pair without
      modification (Open/Closed Principle).
    - ``VoiceManager`` holds no audio, microphone, or speaker logic of
      its own; it purely coordinates calls across its collaborators and
      keeps session state consistent (Single Responsibility Principle).
    - The ``VoiceSessionManager`` is treated as the single source of
      truth for session identity and state. The canonical
      ``VoiceSession`` it creates is passed to both providers'
      ``start_session`` / ``stop_session`` hooks, so providers key their
      internal resources off the same session identity rather than
      minting their own.
    - An optional event publisher callback allows interested observers
      to receive ``VoiceEvent`` notifications for key lifecycle
      moments, without coupling ``VoiceManager`` to any specific event
      bus or messaging framework.

Requires: Python 3.12+
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from src.modules.voice.events import (
    SpeechRecognitionCompleted,
    SpeechRecognitionStarted,
    SpeechSynthesisCompleted,
    SpeechSynthesisStarted,
    VoiceEvent,
    VoiceSessionStarted,
    VoiceSessionStopped,
)
from src.modules.voice.exceptions import VoiceError
from src.modules.voice.models import (
    SpeechRecognitionResult,
    SpeechSynthesisRequest,
    VoiceConfig,
    VoiceSession,
    VoiceState,
)
from src.modules.voice.providers.stt import SpeechToTextProvider
from src.modules.voice.providers.tts import TextToSpeechProvider
from src.modules.voice.session import VoiceSessionManager


class VoiceManager:
    """Central coordinator for the EON Voice module.

    ``VoiceManager`` is the single entry point through which the rest
    of the EON AI Assistant interacts with voice capabilities. It
    coordinates a ``VoiceSessionManager`` and abstract STT/TTS provider
    implementations, but contains no knowledge of any specific
    provider, audio backend, microphone, or speaker implementation.

    Attributes:
        _session_manager: Manages the lifecycle and state of all active
            voice sessions.
        _stt_provider: Abstract speech-to-text provider used for
            transcription.
        _tts_provider: Abstract text-to-speech provider used for
            synthesis.
        _event_publisher: Optional callback invoked with ``VoiceEvent``
            instances at key lifecycle moments.
        _initialized: Whether ``initialize`` has been successfully
            called and ``shutdown`` has not since been called.
    """

    def __init__(
        self,
        session_manager: VoiceSessionManager,
        stt_provider: SpeechToTextProvider,
        tts_provider: TextToSpeechProvider,
        event_publisher: Callable[[VoiceEvent], None] | None = None,
    ) -> None:
        """Initializes the voice manager with its collaborators.

        Args:
            session_manager: Manager responsible for tracking active
                voice sessions.
            stt_provider: Speech-to-text provider used for
                transcription.
            tts_provider: Text-to-speech provider used for synthesis.
            event_publisher: Optional callback invoked with
                ``VoiceEvent`` instances whenever a notable lifecycle
                event occurs. If ``None``, events are not published.
        """
        self._session_manager = session_manager
        self._stt_provider = stt_provider
        self._tts_provider = tts_provider
        self._event_publisher = event_publisher
        self._initialized = False

    @property
    def active_sessions(self) -> list[VoiceSession]:
        """Returns all currently active voice sessions.

        Returns:
            A list of every voice session currently tracked by the
            underlying session manager.
        """
        return self._session_manager.get_sessions()

    @property
    def initialized(self) -> bool:
        """Whether both providers have been successfully initialized."""
        return self._initialized

    @property
    def session_count(self) -> int:
        """Number of active voice sessions currently managed."""
        return self._session_manager.session_count()

    def has_session(
        self,
        session_id: UUID,
    ) -> bool:
        """Returns True if the specified session is currently active."""
        return self._session_manager.has_session(session_id)

    def initialize(self) -> None:
        """Initializes the speech-to-text and text-to-speech providers.

        This method is idempotent: calling it while the manager is
        already initialized has no effect.

        Raises:
            VoiceInitializationError: If either provider fails to
                initialize.
            VoiceProviderError: If either provider reports a failure
                during initialization.
        """
        if self._initialized:
            return
        self._stt_provider.initialize()
        self._tts_provider.initialize()
        self._initialized = True

    def shutdown(self) -> None:
        """Stops all active sessions and shuts down both providers.

        This method is idempotent: calling it while the manager is not
        initialized has no effect beyond clearing any tracked sessions.

        Raises:
            VoiceProviderError: If either provider fails to shut down
                cleanly.
        """
        # for session in self._session_manager.get_sessions():
        #     self._stt_provider.stop_session(session)
        #     self._tts_provider.stop_session(session)
        # self._session_manager.clear()

        # if not self._initialized:
        #     return
        # self._stt_provider.shutdown()
        # self._tts_provider.shutdown()
        # self._initialized = False

        if not self._initialized:
            self._session_manager.clear()
            return

        for session in self._session_manager.get_sessions():
            self._stt_provider.stop_session(session)
            self._tts_provider.stop_session(session)

        self._stt_provider.shutdown()
        self._tts_provider.shutdown()

        self._session_manager.clear()
        self._initialized = False

    def health_check(self) -> bool:
        """Reports whether both providers are currently healthy.

        Returns:
            ``True`` if both the speech-to-text and text-to-speech
            providers report healthy status, ``False`` otherwise.
        """
        return self._stt_provider.health_check() and self._tts_provider.health_check()

    def create_session(self, config: VoiceConfig) -> VoiceSession:
        """Creates a new voice session and prepares both providers for it.

        Args:
            config: Configuration to use for the new session.

        Returns:
            The newly created, canonical voice session.

        Raises:
            VoiceSessionError: If the session cannot be created.
            VoiceProviderError: If either provider fails to prepare its
                session-scoped resources.
        """
        session = self._session_manager.create_session(config)
        self._stt_provider.start_session(session)
        self._tts_provider.start_session(session)
        self._publish(
            VoiceSessionStarted(
                session_id=session.session_id,
                provider_name=self._stt_provider.name,
                language_code=session.config.language_code,
            )
        )
        return session

    def stop_session(self, session_id: UUID) -> None:
        """Stops a voice session and releases both providers' resources.

        Args:
            session_id: Identifier of the session to stop.

        Raises:
            VoiceSessionError: If no session exists for the given
                identifier.
            VoiceProviderError: If either provider fails to release its
                session-scoped resources.
        """
        session = self._session_manager.get_session(session_id)
        self._stt_provider.stop_session(session)
        self._tts_provider.stop_session(session)
        self._session_manager.remove_session(session_id)
        self._publish(
            VoiceSessionStopped(
                session_id=session_id,
                reason="user_stopped",
            )
        )

    def start_listening(self, session_id: UUID) -> VoiceSession:
        """Transitions a session into the listening state.

        Args:
            session_id: Identifier of the session to transition.

        Returns:
            The updated voice session.

        Raises:
            VoiceSessionError: If no session exists for the given
                identifier.
        """
        return self._session_manager.update_session_state(session_id, VoiceState.LISTENING)

    def stop_listening(self, session_id: UUID) -> VoiceSession:
        """Transitions a session out of the listening state.

        Args:
            session_id: Identifier of the session to transition.

        Returns:
            The updated voice session.

        Raises:
            VoiceSessionError: If no session exists for the given
                identifier.
        """
        return self._session_manager.update_session_state(session_id, VoiceState.PROCESSING)

    def transcribe(self, session_id: UUID) -> SpeechRecognitionResult:
        """Transcribes audio for the given session via the STT provider.

        Args:
            session_id: Identifier of the session to transcribe audio
                for.

        Returns:
            The speech recognition result produced by the STT provider.

        Raises:
            VoiceSessionError: If no session exists for the given
                identifier.
            SpeechRecognitionError: If transcription fails.
            VoiceProviderError: If the STT provider fails to fulfill
                the request.
        """
        session = self._session_manager.get_session(session_id)
        self._session_manager.update_session_state(session_id, VoiceState.PROCESSING)
        # self._publish(SpeechRecognitionStarted(session_id=session_id))
        self._publish(SpeechRecognitionStarted(session_id=session_id,language_code=session.config.language_code,))
        try:
            result = self._stt_provider.transcribe(session)
        except VoiceError:
            self._session_manager.update_session_state(session_id, VoiceState.ERROR)
            raise
        self._session_manager.update_session_state(session_id, VoiceState.IDLE)
        self._publish(
            SpeechRecognitionCompleted(
                session_id=session_id,
                transcript=result.transcript,
                confidence=result.confidence,
                is_final=result.is_final,
            )
        )
        return result

    def speak(self, session_id: UUID, request: SpeechSynthesisRequest) -> None:
        """Synthesizes and outputs speech via the TTS provider.

        Args:
            session_id: Identifier of the session to synthesize speech
                for.
            request: The synthesis request describing the text and
                voice parameters to use.

        Raises:
            VoiceSessionError: If no session exists for the given
                identifier.
            SpeechSynthesisError: If synthesis fails.
            VoiceProviderError: If the TTS provider fails to fulfill
                the request.
        """
        session = self._session_manager.get_session(session_id)
        self._session_manager.update_session_state(session_id, VoiceState.SPEAKING)
        self._publish(
            SpeechSynthesisStarted(
                session_id=session_id,
                text=request.text,
                voice_id=request.voice_id,
            )
        )
        try:
            self._tts_provider.speak(session, request)
        except VoiceError:
            self._session_manager.update_session_state(session_id, VoiceState.ERROR)
            raise
        self._session_manager.update_session_state(session_id, VoiceState.IDLE)
        self._publish(
            SpeechSynthesisCompleted(session_id=session_id, output_format=request.output_format)
        )

    def stop_speaking(self, session_id: UUID) -> None:
        """Stops any in-progress speech synthesis for the given session.

        Args:
            session_id: Identifier of the session whose speech should
                be stopped.

        Raises:
            VoiceSessionError: If no session exists for the given
                identifier.
            SpeechSynthesisError: If the in-progress synthesis cannot
                be stopped.
            VoiceProviderError: If the TTS provider fails to fulfill
                the request.
        """
        session = self._session_manager.get_session(session_id)
        self._tts_provider.stop_speaking(session)
        self._session_manager.update_session_state(session_id, VoiceState.IDLE)

    def get_session(self, session_id: UUID) -> VoiceSession:
        """Retrieves a voice session by its identifier.

        Args:
            session_id: Identifier of the session to retrieve.

        Returns:
            The voice session associated with the given identifier.

        Raises:
            VoiceSessionError: If no session exists for the given
                identifier.
        """
        return self._session_manager.get_session(session_id)

    def update_session_state(self, session_id: UUID, state: VoiceState) -> VoiceSession:
        """Updates the state of a voice session.

        Args:
            session_id: Identifier of the session to update.
            state: The new state to assign to the session.

        Returns:
            The updated voice session.

        Raises:
            VoiceSessionError: If no session exists for the given
                identifier.
        """
        return self._session_manager.update_session_state(session_id, state)

    def _publish(self, event: VoiceEvent) -> None:
        """Publishes a voice event if an event publisher is configured.

        Args:
            event: The event to publish.
        """
        if self._event_publisher is not None:
            self._event_publisher(event)
