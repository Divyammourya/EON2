"""
Lifecycle Manager for EON.

Responsible for controlling the lifecycle of all modules.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.core.module_loader import ModuleLoader

logger = get_logger("Lifecycle")


class LifecycleManager:
    """Controls module startup and shutdown."""

    def __init__(self, loader: ModuleLoader) -> None:
        self.loader = loader

        logger.info("Lifecycle Manager initialized.")

    def start(self) -> None:
        """Start every registered module."""

        logger.info("Initializing modules...")

        self.loader.initialize_modules()

        logger.info("Starting modules...")

        self.loader.start_modules()

        logger.info("Lifecycle startup complete.")

    def shutdown(self) -> None:
        """Shutdown every registered module."""

        logger.info("Stopping modules...")

        self.loader.stop_modules()

        logger.info("Shutting down modules...")

        self.loader.shutdown_modules()

        logger.info("Lifecycle shutdown complete.")
