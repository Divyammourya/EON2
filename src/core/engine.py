
"""
Core Engine for EON.
"""

from __future__ import annotations

from src.core.config import ConfigManager
from src.core.container import ServiceContainer
from src.core.events import EventBus
from src.core.logger import get_logger
from src.core.state import EONState, StateManager
from src.core.module_loader import ModuleLoader
from src.modules.system.system_module import SystemModule
from src.core.lifecycle import LifecycleManager

from src.interfaces.module import Module

logger = get_logger("Engine")


class Engine:
    """Main application engine."""

    def __init__(self) -> None:
        logger.info("Creating Engine...")

        self.services = ServiceContainer()

        # Create services
        config = ConfigManager()
        state = StateManager()
        events = EventBus()

        # Register services
        self.services.register("config", config)
        self.services.register("state", state)
        self.services.register("events", events)

        self.module_loader = ModuleLoader()

        system = SystemModule()

        self.module_loader.register(system)

        self.lifecycle = LifecycleManager(self.module_loader)

    def start(self) -> None:
        """Start EON."""

        logger.info("Starting Engine...")

        state: StateManager = self.services.get("state")
        config: ConfigManager = self.services.get("config")

        state.set_state(EONState.READY)

        self.lifecycle.start()
        logger.info(
             "Module Health: %s",
             self.module_loader.health_report(),
        )

        logger.info(
            "EON %s is READY.",
            config.get("version"),
        )

        logger.info(
            "Registered Services: %s",
            ", ".join(self.services.list_services()),
        )

    def shutdown(self) -> None:
        """Shutdown EON."""

        logger.info("Shutting down Engine...")

        state: StateManager = self.services.get("state")

        state.set_state(EONState.SHUTTING_DOWN)

        self.lifecycle.shutdown()

        logger.info("Engine stopped.")

    def register_module(self,module: Module) -> None:
        """
        Register a module with the engine.
        """

        self.module_loader.register(module)
