"""
Desktop Companion (Hologram) Module.

Integrates the hologram overlay into the EON module lifecycle.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.interfaces.module import Module
from src.ui.hologram.service import DesktopCompanionService

logger = get_logger("Hologram")


class HologramModule(Module):
    """
    Desktop companion hologram module lifecycle implementation.
    """

    def __init__(
        self,
        service: DesktopCompanionService,
    ) -> None:
        self._service = service

    @property
    def name(self) -> str:
        return "Hologram"

    def initialize(self) -> None:
        logger.info("Initializing Hologram module.")
        self._service.initialize()

    def start(self) -> None:
        self._service.start()

    def stop(self) -> None:
        self._service.stop()

    def shutdown(self) -> None:
        logger.info("Shutting down Hologram module.")
        self._service.shutdown()

    def health_check(self) -> bool:
        return self._service.health_check()
