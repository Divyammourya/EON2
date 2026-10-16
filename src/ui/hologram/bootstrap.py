"""
Hologram module bootstrap.

Responsible for registering the Desktop Companion (hologram overlay)
module with the Engine.
"""

from __future__ import annotations

from src.core.container import ServiceContainer
from src.core.engine import Engine

from src.ui.hologram.module import HologramModule
from src.ui.hologram.service import DesktopCompanionService


def register(
    engine: Engine,
    container: ServiceContainer,
) -> None:
    """
    Register the Desktop Companion (hologram overlay) module.
    """

    service: DesktopCompanionService = container.get("hologram")

    module = HologramModule(
        service=service,
    )

    engine.module_loader.register(module)
