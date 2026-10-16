"""
Speech-to-Text Provider Interface.

Defines the contract implemented by every speech-to-text provider.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterator

from src.modules.voice.models import (
    SpeechRecognitionResult,
    VoiceSession,
)
from src.modules.voice.providers.base import VoiceProvider


class SpeechToTextProvider(VoiceProvider):
    """
    Abstract base class for every speech-to-text provider.
    """

    @abstractmethod
    def transcribe_stream(
        self,
        session: VoiceSession,
    ) -> Iterator[SpeechRecognitionResult]:
        """
        Stream speech recognition results from a voice session.
        """
