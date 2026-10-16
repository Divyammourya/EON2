"""
Voice Exceptions.

Custom exception hierarchy for the Voice subsystem.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


class VoiceError(Exception):
    """
    Base exception for all voice-related errors.
    """

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | details={self.details}"

        return self.message


class VoiceInitializationError(VoiceError):
    """
    Raised when the Voice module fails to initialize.
    """


class VoiceProviderError(VoiceError):
    """
    Raised when an underlying voice provider fails.
    """

    def __init__(
        self,
        message: str,
        *,
        provider_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            details=details,
        )

        self.provider_name = provider_name


class SpeechRecognitionError(VoiceError):
    """
    Raised when speech recognition fails.
    """


class SpeechSynthesisError(VoiceError):
    """
    Raised when speech synthesis fails.
    """


class MicrophoneError(VoiceError):
    """
    Raised when microphone input fails.
    """


class SpeakerError(VoiceError):
    """
    Raised when speaker output fails.
    """


class VoiceSessionError(VoiceError):
    """
    Raised for errors related to the lifecycle of a voice session.
    """

    def __init__(
        self,
        message: str,
        *,
        session_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            details=details,
        )

        self.session_id = session_id
