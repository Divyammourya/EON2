"""
Proactive module bootstrap.

Responsible for registering the Proactive Speech module with the
Engine.
"""

from __future__ import annotations

from src.core.engine import Engine
from src.core.container import ServiceContainer

from src.modules.proactive.module import ProactiveModule
from src.modules.proactive.service import ProactiveService


def register(
    engine: Engine,
    container: ServiceContainer,
) -> None:
    """
    Register the Proactive Speech module.
    """

    service: ProactiveService = container.get("proactive")

    module = ProactiveModule(
        service=service,
    )

    engine.module_loader.register(module)
