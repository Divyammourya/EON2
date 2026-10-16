"""
Memory Module.

Integrates the Memory subsystem into the EON module lifecycle.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.interfaces.module import Module
from src.modules.memory.service import MemoryService

logger = get_logger("Memory")


class MemoryModule(Module):
    """
    Memory module lifecycle implementation.
    """

    def __init__(
        self,
        service: MemoryService,
    ) -> None:
        self._service = service

    @property
    def name(self) -> str:
        return "Memory"

    def initialize(self) -> None:
        logger.info("Initializing Memory module.")
        self._service.initialize()

    def start(self) -> None:
        logger.info("Memory module started.")

    def stop(self) -> None:
        logger.info("Memory module stopped.")

    def shutdown(self) -> None:
        logger.info("Shutting down Memory module.")
        self._service.shutdown()

    def health_check(self) -> bool:
        return self._service.health_check()
