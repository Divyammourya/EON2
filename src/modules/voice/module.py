"""
Voice Module.

Integrates the Voice subsystem into the EON module lifecycle.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.interfaces.module import Module
from src.modules.voice.service import VoiceService

logger = get_logger("Voice")


class VoiceModule(Module):
    """
    Voice module lifecycle implementation.
    """

    def __init__(
        self,
        service: VoiceService,
    ) -> None:
        self._service = service

    @property
    def name(self) -> str:
        return "Voice"

    def initialize(self) -> None:
        logger.info("Initializing Voice module.")
        self._service.initialize()

    def start(self) -> None:
        logger.info("Voice module started.")

    def stop(self) -> None:
        logger.info("Voice module stopped.")

    def shutdown(self) -> None:
        logger.info("Shutting down Voice module.")
        self._service.shutdown()

    def health_check(self) -> bool:
        return self._service.health_check()
