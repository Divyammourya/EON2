"""
Voice Events.

Domain events for the Voice subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(slots=True, kw_only=True)
class VoiceEvent:
    """
    Base class for every voice event.
    """

    session_id: UUID
    event_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(slots=True, kw_only=True)
class VoiceSessionStarted(VoiceEvent):
    """
    Emitted when a voice session starts.
    """

    provider_name: str | None = None
    language_code: str = "en-US"


@dataclass(slots=True, kw_only=True)
class VoiceSessionStopped(VoiceEvent):
    """
    Emitted when a voice session stops.
    """

    reason: str | None = None


@dataclass(slots=True, kw_only=True)
class SpeechRecognitionStarted(VoiceEvent):
    """
    Emitted when speech recognition begins.
    """

    language_code: str = "en-US"


@dataclass(slots=True, kw_only=True)
class SpeechRecognitionCompleted(VoiceEvent):
    """
    Emitted when speech recognition completes.
    """

    transcript: str
    confidence: float = 0.0
    is_final: bool = True


@dataclass(slots=True, kw_only=True)
class SpeechSynthesisStarted(VoiceEvent):
    """
    Emitted when speech synthesis begins.
    """

    text: str
    voice_id: str | None = None


@dataclass(slots=True, kw_only=True)
class SpeechSynthesisCompleted(VoiceEvent):
    """
    Emitted when speech synthesis completes.
    """

    output_format: str = "wav"
    duration_seconds: float | None = None
