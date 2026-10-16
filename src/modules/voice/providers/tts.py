"""
Abstract Text-to-Speech provider interface for EON.

Defines the contract that every Text-to-Speech provider
(Piper, OpenAI TTS, ElevenLabs, Azure, etc.) must implement.
"""

from __future__ import annotations

from abc import abstractmethod

from src.modules.voice.models import (
    SpeechSynthesisRequest,
    VoiceSession,
)
from src.modules.voice.providers.base import VoiceProvider


class TextToSpeechProvider(VoiceProvider):
    """
    Base interface for all Text-to-Speech providers.

    Extends the generic VoiceProvider with TTS-specific
    capabilities.
    """

    @abstractmethod
    def speak(
        self,
        session: VoiceSession,
        request: SpeechSynthesisRequest,
    ) -> None:
        """
        Convert text into speech.

        Args:
            session:
                Active voice session.

            request:
                Speech synthesis request.

        Raises:
            SpeechSynthesisError
            VoiceSessionError
            VoiceProviderError
        """
        raise NotImplementedError

    @abstractmethod
    def stop_speaking(
        self,
        session: VoiceSession,
    ) -> None:
        """
        Immediately stop any speech currently playing.

        Args:
            session:
                Active voice session.

        Raises:
            SpeechSynthesisError
            VoiceSessionError
            VoiceProviderError
        """
        raise NotImplementedError

    @abstractmethod
    def is_speaking(
        self,
        session: VoiceSession,
    ) -> bool:
        """
        Return whether the provider is currently speaking.

        Args:
            session:
                Active voice session.

        Returns:
            True if speech playback is active.
        """
        raise NotImplementedError
