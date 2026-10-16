"""
Memory module bootstrap.

Responsible for registering the Memory module with the Engine.
"""

from __future__ import annotations

from src.core.engine import Engine
from src.core.container import ServiceContainer

from src.modules.memory.module import MemoryModule
from src.modules.memory.service import MemoryService


def register(
    engine: Engine,
    container: ServiceContainer,
) -> None:
    """
    Register the Memory module.
    """

    service: MemoryService = container.get("memory")

    module = MemoryModule(
        service=service,
    )

    engine.module_loader.register(module)
