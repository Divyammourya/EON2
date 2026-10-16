"""
Module Loader for EON.

Responsible for registering and managing application modules.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.interfaces.module import Module

logger = get_logger("ModuleLoader")


class ModuleLoader:
    """Loads and manages EON modules."""

    def __init__(self) -> None:
        self._modules: dict[str, Module] = {}

        logger.info("Module Loader initialized.")

    def register(self, module: Module) -> None:
        """Register a module."""

        if module.name in self._modules:
            raise ValueError(
                f"Module '{module.name}' already registered."
            )

        self._modules[module.name] = module

        logger.info("Registered module: %s", module.name)

    def initialize_modules(self) -> None:
        """Initialize all modules."""

        for module in self._modules.values():
            module.initialize()

    def start_modules(self) -> None:
        """Start all modules."""

        for module in self._modules.values():
            module.start()

    def stop_modules(self) -> None:
        """Stop all modules."""

        for module in self._modules.values():
            module.stop()

    def shutdown_modules(self) -> None:
        """Shutdown all modules."""

        for module in self._modules.values():
            module.shutdown()

    def health_report(self) -> dict[str, bool]:
        """Return health of every module."""

        return {
            module.name: module.health_check()
            for module in self._modules.values()
        }
