"""Data models for the Voice subsystem.

This module defines the core, framework-agnostic data structures used
throughout the Voice subsystem: configuration, session state, speech
recognition results, and speech synthesis requests.

Design notes:
    - This module contains **only** data models. No business logic,
      validation beyond basic type/shape enforcement, or I/O is
      performed here (Single Responsibility Principle).
    - Provider-specific behavior is represented via ``VoiceProviderType``
      and injected configuration rather than subclassing, so new
      providers can be added without modifying existing models
      (Open/Closed Principle).
    - All models are immutable-by-default where practical (via
      ``frozen=False`` but ``slots=True`` for memory efficiency); callers
      that need immutability can wrap or freeze at a higher layer.

Requires: Python 3.12+
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import Any
from uuid import UUID, uuid4


@unique
class VoiceState(Enum):
    """Represents the lifecycle state of a voice session.

    Attributes:
        IDLE: The session exists but no activity is occurring.
        LISTENING: The session is actively capturing audio input.
        PROCESSING: Captured audio is being processed (e.g. transcribed).
        SPEAKING: The session is actively playing synthesized audio.
        PAUSED: The session is temporarily suspended.
        ERROR: The session has encountered an unrecoverable error.
        TERMINATED: The session has ended and is no longer usable.
    """

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


@unique
class VoiceProviderType(Enum):
    """Identifies the backing provider/engine for voice capabilities.

    Attributes:
        AMAZON_POLLY: Amazon Polly text-to-speech service.
        GOOGLE_CLOUD: Google Cloud Speech-to-Text / Text-to-Speech.
        AZURE_COGNITIVE: Microsoft Azure Cognitive Services Speech.
        OPENAI_REALTIME: OpenAI realtime voice API.
        ELEVENLABS: ElevenLabs speech synthesis service.
        LOCAL_WHISPER: Locally hosted Whisper model for recognition.
        CUSTOM: A user-defined or proprietary provider implementation.

    """

    FASTER_WHISPER = "faster_whisper"
    PIPER = "piper"
    OPENAI = "openai"
    OLLAMA = "ollama"
    CUSTOM = "custom"


@dataclass(slots=True)
class VoiceConfig:
    """Configuration required to initialize a voice provider/session.

    This model is intentionally provider-agnostic. Provider-specific
    options that do not fit the common fields should be placed in
    ``extra_options`` so that new providers do not require changes to
    this class (Open/Closed Principle).

    Attributes:
        provider_type: The voice provider/engine to use.
        language_code: BCP-47 language code (e.g. "en-US").
        voice_id: Identifier of the specific voice to use for synthesis,
            if applicable.
        sample_rate_hz: Audio sample rate in hertz.
        enable_interim_results: Whether partial/interim recognition
            results should be emitted during processing.
        max_alternatives: Maximum number of alternative transcriptions
            to request from the recognition provider.
        timeout_seconds: Maximum time, in seconds, to wait for a
            provider operation before it is considered failed.
        api_key: Optional API key/credential reference for the provider.
            Should generally be a reference/secret name rather than a
            raw secret value.
        extra_options: Free-form provider-specific configuration values
            not covered by the standard fields.
    """

    provider_type: VoiceProviderType
    language_code: str = "en-US"
    voice_id: str | None = None
    sample_rate_hz: int = 16_000
    enable_interim_results: bool = False
    max_alternatives: int = 1
    timeout_seconds: float = 30.0
    extra_options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VoiceSession:
    """Represents a single, stateful voice interaction session.

    Attributes:
        session_id: Unique identifier for this session.
        config: The configuration used to create this session.
        state: The current lifecycle state of the session.
        created_at: UTC timestamp when the session was created.
        updated_at: UTC timestamp when the session was last updated.
        user_id: Optional identifier of the user this session belongs to.
        metadata: Free-form, caller-supplied metadata associated with
            the session (e.g. correlation IDs, client info).
    """

    config: VoiceConfig
    session_id: UUID = field(default_factory=uuid4)
    state: VoiceState = VoiceState.IDLE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SpeechRecognitionResult:
    """Represents the result of a speech-to-text recognition operation.

    Attributes:
        result_id: Unique identifier for this result.
        session_id: Identifier of the session this result belongs to.
        transcript: The recognized text.
        confidence: Confidence score for the transcript, in the range
            [0.0, 1.0].
        is_final: Whether this is a final result (``True``) or an
            interim/partial result (``False``).
        alternatives: Alternative transcripts with their respective
            confidence scores, ordered by descending confidence.
        language_code: BCP-47 language code of the recognized speech.
        created_at: UTC timestamp when this result was produced.
    """

    session_id: UUID
    transcript: str
    result_id: UUID = field(default_factory=uuid4)
    confidence: float = 0.0
    is_final: bool = True
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    language_code: str = "en-US"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class SpeechSynthesisRequest:
    """Represents a request to synthesize speech from text.

    Attributes:
        request_id: Unique identifier for this request.
        session_id: Identifier of the session this request belongs to.
        text: The text to be synthesized into speech.
        voice_id: Identifier of the voice to use, overriding the
            session's configured voice if provided.
        language_code: BCP-47 language code for synthesis.
        speaking_rate: Relative speaking rate, where ``1.0`` is normal
            speed.
        pitch: Relative pitch adjustment, where ``0.0`` is unchanged.
        output_format: Desired audio output format (e.g. "mp3", "wav",
            "pcm").
        created_at: UTC timestamp when this request was created.
    """

    session_id: UUID
    text: str
    request_id: UUID = field(default_factory=uuid4)
    voice_id: str | None = None
    language_code: str = "en-US"
    speaking_rate: float = 1.0
    pitch: float = 0.0
    output_format: str = "wav"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
