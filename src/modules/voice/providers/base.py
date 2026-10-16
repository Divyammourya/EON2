"""
Voice Provider Interface.

Defines the contract implemented by every voice provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.modules.voice.models import (
    SpeechRecognitionResult,
    SpeechSynthesisRequest,
    VoiceConfig,
    VoiceSession,
)


class VoiceProvider(ABC):
    """
    Abstract base class for every voice provider.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the provider name.
        """

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the provider.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """
        Shutdown the provider.
        """

    @abstractmethod
    def health_check(self) -> bool:
        """
        Return whether the provider is healthy.
        """

    @abstractmethod
    def start_session(
        self,
        config: VoiceConfig,
    ) -> VoiceSession:
        """
        Start a voice session.
        """

    @abstractmethod
    def stop_session(
        self,
        session: VoiceSession,
    ) -> None:
        """
        Stop a voice session.
        """

    @abstractmethod
    def transcribe(
        self,
        session: VoiceSession,
    ) -> SpeechRecognitionResult:
        """
        Transcribe speech from a voice session.
        """

    @abstractmethod
    def speak(
        self,
        session: VoiceSession,
        request: SpeechSynthesisRequest,
    ) -> None:
        """
        Synthesize speech for a voice session.
        """
