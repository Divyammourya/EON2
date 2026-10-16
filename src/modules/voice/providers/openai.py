"""OpenAI backed speech provider for the EON Voice module.

This module provides ``OpenAIProvider``, a concrete implementation of
``VoiceProvider`` backed by OpenAI's hosted speech APIs. Unlike
``FasterWhisperProvider`` (speech-to-text only) and ``PiperProvider``
(text-to-speech only), ``OpenAIProvider`` supports both speech
recognition and speech synthesis through a single hosted service,
since OpenAI exposes both capabilities behind one authenticated
client.

Design notes:
    - ``OpenAIProvider`` is the only place in the Voice module that
      imports the ``openai`` package. All other Voice components
      depend solely on the ``VoiceProvider`` abstraction, keeping the
      concrete SDK isolated behind a single implementation (Dependency
      Inversion Principle). Replacing OpenAI with another hosted
      speech vendor requires writing a new ``VoiceProvider``
      implementation; no other code changes.
    - The underlying ``OpenAI`` client is constructed lazily, on first
      use, so constructing this provider performs no network activity
      and is cheap and side-effect free. Client construction is
      guarded by a lock using the double-checked locking pattern to
      remain safe under concurrent access, mirroring
      ``FasterWhisperProvider`` and ``PiperProvider``.
    - API calls are serialized behind a dedicated inference lock, since
      a single shared client should not be driven concurrently by
      multiple callers issuing overlapping requests from this
      provider.
    - All exceptions raised by the ``openai`` SDK, the network layer,
      or byte-handling code are caught at the boundary of this class
      and translated into the project's own exception types
      (``VoiceInitializationError``, ``VoiceProviderError``,
      ``SpeechRecognitionError``, ``SpeechSynthesisError``,
      ``VoiceSessionError``); no third-party exception type ever
      escapes this module.
    - Audio to be transcribed is expected as raw bytes stored under
      ``session.metadata["audio_bytes"]``, matching the convention
      established by ``FasterWhisperProvider``. Synthesized audio is
      written back to the same key as raw WAV bytes, matching the
      convention established by ``PiperProvider``. This provider never
      plays audio and never writes files to disk.

Requires: Python 3.12+, openai
"""

from __future__ import annotations

import io
import math
import threading
from collections.abc import Iterator
from uuid import UUID

from openai import OpenAI

from src.modules.voice.exceptions import (
    SpeechRecognitionError,
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
from src.modules.voice.providers.base import VoiceProvider

_AUDIO_METADATA_KEY = "audio_bytes"
_SYNTHESIS_AUDIO_FILENAME = "speech.wav"
_TRANSCRIPTION_AUDIO_FILENAME = "audio.wav"
_SYNTHESIS_RESPONSE_FORMAT = "wav"
_DEFAULT_TRANSCRIPTION_CONFIDENCE = 1.0
_MIN_SPEECH_SPEED = 0.25
_MAX_SPEECH_SPEED = 4.0


class OpenAIProvider(VoiceProvider):
    """Speech provider backed by OpenAI's hosted transcription and TTS APIs.

    ``OpenAIProvider`` transcribes audio using OpenAI's speech
    transcription endpoint and synthesizes speech using OpenAI's speech
    generation endpoint, both accessed through a single lazily
    constructed ``OpenAI`` client. Because a single vendor provides
    both capabilities, this provider implements the full
    ``VoiceProvider`` contract directly rather than specializing
    through ``SpeechToTextProvider`` or ``TextToSpeechProvider``.

    Attributes:
        _api_key: API key used to authenticate with OpenAI.
        _organization: Optional OpenAI organization identifier to
            attribute requests to.
        _project: Optional OpenAI project identifier to attribute
            requests to.
        _transcription_model: Name of the model used for speech
            transcription (e.g. "gpt-4o-mini-transcribe").
        _speech_model: Name of the model used for speech synthesis
            (e.g. "gpt-4o-mini-tts").
        _voice: Default OpenAI voice identifier used for synthesis when
            a request does not specify one (e.g. "alloy").
        _client: The lazily constructed ``OpenAI`` client, or ``None``
            if not yet constructed.
        _load_lock: Guards lazy, thread-safe construction of
            ``_client``.
        _inference_lock: Serializes calls into the OpenAI API to avoid
            overlapping concurrent requests from this provider.
        _active_session_ids: Identifiers of sessions currently started
            on this provider.
        _sessions_lock: Guards concurrent access to
            ``_active_session_ids``.
    """

    def __init__(
        self,
        api_key: str,
        organization: str | None = None,
        project: str | None = None,
        transcription_model: str = "gpt-4o-mini-transcribe",
        speech_model: str = "gpt-4o-mini-tts",
        voice: str = "alloy",
    ) -> None:
        """Configures the provider without constructing the client yet.

        Args:
            api_key: API key used to authenticate with OpenAI. Must be
                a non-empty string.
            organization: Optional OpenAI organization identifier to
                attribute requests to.
            project: Optional OpenAI project identifier to attribute
                requests to.
            transcription_model: Name of the model used for speech
                transcription. Must be a non-empty string.
            speech_model: Name of the model used for speech synthesis.
                Must be a non-empty string.
            voice: Default OpenAI voice identifier used for synthesis
                when a request does not specify one. Must be a
                non-empty string.

        Raises:
            ValueError: If any argument fails validation.
        """
        self._validate_constructor_args(
            api_key,
            organization,
            project,
            transcription_model,
            speech_model,
            voice,
        )
        self._api_key = api_key
        self._organization = organization
        self._project = project
        self._transcription_model = transcription_model
        self._speech_model = speech_model
        self._voice = voice

        self._client: OpenAI | None = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

        self._active_session_ids: set[UUID] = set()
        self._sessions_lock = threading.Lock()

    @property
    def name(self) -> str:
        """Returns the unique, human-readable name of this provider.

        Returns:
            The literal string "openai".
        """
        return "openai"

    def initialize(self) -> None:
        """Eagerly constructs the underlying OpenAI client.

        Calling this method is optional: the client is constructed
        lazily on first use regardless. Calling it explicitly allows
        initialization failures to surface before any session is
        created.

        Raises:
            VoiceInitializationError: If the client fails to
                construct.
        """
        self._get_client()

    def shutdown(self) -> None:
        """Releases the OpenAI client and clears active sessions.

        Sets the cached client reference to ``None`` and clears all
        active session registrations.
        """
        with self._load_lock:
            self._client = None
        with self._sessions_lock:
            self._active_session_ids.clear()

    def health_check(self) -> bool:
        """Reports whether the provider client has been constructed.

        This check is local and performs no network activity; it
        reports whether the client has already been initialized, not
        whether OpenAI's APIs are currently reachable.

        Returns:
            ``True`` if the OpenAI client has been successfully
            constructed, ``False`` otherwise.
        """
        return self._client is not None

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
            session: The voice session to transcribe audio for. Must
                be registered on this provider. The audio to transcribe
                must be present as non-empty bytes under
                ``session.metadata["audio_bytes"]``.

        Returns:
            A single, final speech recognition result containing the
            full transcript. OpenAI's transcription endpoint does not
            report a confidence score, so ``confidence`` is always
            ``1.0`` for a successful call.

        Raises:
            VoiceSessionError: If the session is not registered on this
                provider.
            SpeechRecognitionError: If the audio is missing, malformed,
                or transcription otherwise fails.
            VoiceInitializationError: If the client fails to construct.
        """
        self._ensure_session_active(session.session_id)
        audio_bytes = self._extract_audio_bytes(session)
        transcript = self._transcribe_audio(audio_bytes, session)

        return SpeechRecognitionResult(
            session_id=session.session_id,
            transcript=transcript,
            confidence=_DEFAULT_TRANSCRIPTION_CONFIDENCE,
            is_final=True,
            language_code=session.config.language_code,
        )

    def transcribe_stream(
        self,
        session: VoiceSession,
    ) -> Iterator[SpeechRecognitionResult]:
        """Streams transcription results for a session.

        OpenAI's transcription endpoint is request-response rather than
        streaming, so this method performs one full transcription and
        yields its single, final result.

        Args:
            session: The voice session to transcribe audio for. Must
                be registered on this provider. The audio to transcribe
                must be present as non-empty bytes under
                ``session.metadata["audio_bytes"]``.

        Yields:
            The single, final speech recognition result produced for
            the session.

        Raises:
            VoiceSessionError: If the session is not registered on this
                provider.
            SpeechRecognitionError: If the audio is missing, malformed,
                or transcription otherwise fails.
            VoiceInitializationError: If the client fails to construct.
        """
        yield self.transcribe(session)

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
            VoiceInitializationError: If the client fails to construct.
        """
        self._ensure_session_active(session.session_id)
        session.metadata[_AUDIO_METADATA_KEY] = self._synthesize_audio(request)

    def stop_speaking(self, session: VoiceSession) -> None:
        """Validates that a session may have its speech synthesis stopped.

        OpenAI's speech synthesis endpoint is synchronous: a call to
        ``speak`` completes fully before returning, so there is no
        in-progress operation to interrupt. This method exists to
        satisfy the ``VoiceProvider`` contract and to surface a clear
        error if called against an unregistered session.

        Args:
            session: The voice session whose speech should be stopped.

        Raises:
            VoiceSessionError: If the session is not registered on this
                provider.
        """
        self._ensure_session_active(session.session_id)

    @staticmethod
    def _validate_constructor_args(
        api_key: str,
        organization: str | None,
        project: str | None,
        transcription_model: str,
        speech_model: str,
        voice: str,
    ) -> None:
        """Validates constructor arguments before they are stored.

        Args:
            api_key: Candidate OpenAI API key.
            organization: Candidate OpenAI organization identifier.
            project: Candidate OpenAI project identifier.
            transcription_model: Candidate transcription model name.
            speech_model: Candidate speech synthesis model name.
            voice: Candidate default voice identifier.

        Raises:
            ValueError: If any argument is invalid.
        """
        if not api_key or not api_key.strip():
            raise ValueError("api_key must be a non-empty string.")
        if organization is not None and not organization.strip():
            raise ValueError("organization must be a non-empty string or None.")
        if project is not None and not project.strip():
            raise ValueError("project must be a non-empty string or None.")
        if not transcription_model or not transcription_model.strip():
            raise ValueError("transcription_model must be a non-empty string.")
        if not speech_model or not speech_model.strip():
            raise ValueError("speech_model must be a non-empty string.")
        if not voice or not voice.strip():
            raise ValueError("voice must be a non-empty string.")

    def _get_client(self) -> OpenAI:
        """Returns the OpenAI client, constructing it if necessary.

        Uses the double-checked locking pattern so the client is
        constructed at most once, even under concurrent access. No
        network activity occurs during construction.

        Returns:
            The constructed ``OpenAI`` client instance.

        Raises:
            VoiceInitializationError: If the client fails to
                construct.
        """
        if self._client is not None:
            return self._client
        with self._load_lock:
            if self._client is None:
                try:
                    self._client = OpenAI(
                        api_key=self._api_key,
                        organization=self._organization,
                        project=self._project,
                    )
                except Exception as exc:
                    raise VoiceInitializationError(
                        "Failed to construct the OpenAI client.",
                        details={
                            "transcription_model": self._transcription_model,
                            "speech_model": self._speech_model,
                        },
                    ) from exc
        return self._client

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
        """Extracts raw audio bytes from a session's metadata.

        Args:
            session: The voice session to extract audio from.

        Returns:
            The raw audio bytes associated with the session.

        Raises:
            SpeechRecognitionError: If no audio bytes are present, the
                stored value is not of type ``bytes``, or the bytes are
                empty.
        """
        audio_bytes = session.metadata.get(_AUDIO_METADATA_KEY)
        if not isinstance(audio_bytes, bytes) or not audio_bytes:
            raise SpeechRecognitionError(
                "No audio bytes were found on the session to transcribe.",
                details={"session_id": str(session.session_id)},
            )
        return audio_bytes

    def _transcribe_audio(self, audio_bytes: bytes, session: VoiceSession) -> str:
        """Sends audio bytes to OpenAI's transcription endpoint.

        Args:
            audio_bytes: Raw audio bytes to transcribe.
            session: The voice session the audio belongs to, used only
                to enrich error details for debugging.

        Returns:
            The transcript text returned by the transcription
            endpoint.

        Raises:
            SpeechRecognitionError: If the transcription request
                fails.
            VoiceInitializationError: If the client fails to
                construct.
        """
        client = self._get_client()
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = _TRANSCRIPTION_AUDIO_FILENAME

        with self._inference_lock:
            try:
                response = client.audio.transcriptions.create(
                    model=self._transcription_model,
                    file=audio_file,
                )
            except Exception as exc:
                raise SpeechRecognitionError(
                    "OpenAI failed to transcribe the provided audio.",
                    details={
                        "session_id": str(session.session_id),
                        "audio_bytes": len(audio_bytes),
                    },
                ) from exc

        return response.text

    def _synthesize_audio(self, request: SpeechSynthesisRequest) -> bytes:
        """Sends a synthesis request to OpenAI's speech endpoint.

        Args:
            request: The synthesis request describing the text and
                voice parameters to use.

        Returns:
            The synthesized audio, encoded as WAV bytes.

        Raises:
            SpeechSynthesisError: If the request text is empty or
                contains only whitespace, if ``speaking_rate`` is out
                of OpenAI's supported range, or if synthesis otherwise
                fails.
            VoiceInitializationError: If the client fails to
                construct.
        """
        text = request.text
        self._validate_synthesis_text(text)
        speed = self._resolve_speech_speed(request.speaking_rate)
        voice_id = self._resolve_voice_id(request.voice_id)
        client = self._get_client()

        with self._inference_lock:
            try:
                response = client.audio.speech.create(
                    model=self._speech_model,
                    voice=voice_id,
                    input=text,
                    speed=speed,
                    response_format=_SYNTHESIS_RESPONSE_FORMAT,
                )
            except Exception as exc:
                raise SpeechSynthesisError(
                    "OpenAI failed to synthesize the requested text.",
                    details={"request_id": str(request.request_id)},
                ) from exc

        return self._extract_synthesis_bytes(response, request)

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

    def _resolve_voice_id(self, voice_id: str | None) -> str:
        """Resolves the OpenAI voice identifier to use for a request.

        An explicitly empty or whitespace-only ``voice_id`` is treated
        as an error rather than silently falling back to the provider's
        default, since it most likely indicates a caller mistake.
        ``None`` is treated as "no preference" and falls back to the
        provider's configured default voice.

        Args:
            voice_id: The voice identifier requested by the caller, or
                ``None`` to use the provider's configured default.

        Returns:
            The resolved, non-empty voice identifier to use.

        Raises:
            SpeechSynthesisError: If ``voice_id`` is an empty or
                whitespace-only string.
        """
        if voice_id is None:
            return self._voice
        if not voice_id.strip():
            raise SpeechSynthesisError("voice_id must not be an empty string.")
        return voice_id

    def _extract_synthesis_bytes(
        self,
        response: object,
        request: SpeechSynthesisRequest,
    ) -> bytes:
        """Extracts raw audio bytes from an OpenAI speech API response.

        The OpenAI SDK has exposed synthesized audio through different
        attributes across versions. This helper checks the known
        shapes in order of preference so a future SDK upgrade that
        changes the response type does not silently break synthesis.

        Args:
            response: The response object returned by
                ``client.audio.speech.create``.
            request: The synthesis request that produced this response,
                used only to enrich error details for debugging.

        Returns:
            The synthesized audio, encoded as WAV bytes.

        Raises:
            SpeechSynthesisError: If no known byte-yielding attribute
                is found on the response.
        """
        content = getattr(response, "content", None)
        if isinstance(content, bytes):
            return content

        read_method = getattr(response, "read", None)
        if callable(read_method):
            try:
                data = read_method()
            except Exception as exc:
                raise SpeechSynthesisError(
                    "Failed to read synthesized audio from the OpenAI response.",
                    details={"request_id": str(request.request_id)},
                ) from exc
            if isinstance(data, bytes):
                return data

        raise SpeechSynthesisError(
            "OpenAI response did not expose synthesized audio in a "
            "recognized format. The installed openai SDK version may "
            "be incompatible with this provider.",
            details={"request_id": str(request.request_id)},
        )

    @staticmethod
    def _resolve_speech_speed(speaking_rate: float) -> float:
        """Validates a speaking rate against OpenAI's supported range.

        Args:
            speaking_rate: Relative speaking rate, where ``1.0`` is
                normal speed.

        Returns:
            The validated speaking rate, unchanged, ready to be passed
            as OpenAI's ``speed`` parameter.

        Raises:
            SpeechSynthesisError: If ``speaking_rate`` is not a finite
                number, or falls outside OpenAI's supported range of
                ``0.25`` to ``4.0``.
        """
        if not math.isfinite(speaking_rate):
            raise SpeechSynthesisError(
                "speaking_rate must be a finite number.",
                details={"speaking_rate": speaking_rate},
            )
        if not _MIN_SPEECH_SPEED <= speaking_rate <= _MAX_SPEECH_SPEED:
            raise SpeechSynthesisError(
                f"speaking_rate must be between {_MIN_SPEECH_SPEED} and "
                f"{_MAX_SPEECH_SPEED}.",
                details={"speaking_rate": speaking_rate},
            )
        return speaking_rate
