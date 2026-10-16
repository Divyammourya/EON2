"""
Proactive Speech Module.

Integrates the Proactive Speech subsystem into the EON module
lifecycle.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.interfaces.module import Module
from src.modules.proactive.service import ProactiveService

logger = get_logger("Proactive")


class ProactiveModule(Module):
    """
    Proactive Speech module lifecycle implementation.
    """

    def __init__(
        self,
        service: ProactiveService,
    ) -> None:
        self._service = service

    @property
    def name(self) -> str:
        return "Proactive"

    def initialize(self) -> None:
        logger.info("Initializing Proactive module.")
        self._service.initialize()

    def start(self) -> None:
        self._service.start()

    def stop(self) -> None:
        self._service.stop()

    def shutdown(self) -> None:
        logger.info("Shutting down Proactive module.")
        self._service.shutdown()

    def health_check(self) -> bool:
        return self._service.health_check()
