"""
Module registration for EON.

Coordinates registration of all lifecycle-managed modules.
"""

from __future__ import annotations

from src.core.engine import Engine
from src.core.container import ServiceContainer

from src.modules.memory.bootstrap import register as register_memory
from src.modules.voice.bootstrap import register as register_voice
from src.modules.proactive.bootstrap import register as register_proactive
from src.ui.hologram.bootstrap import register as register_hologram


def register_modules(
    engine: Engine,
    container: ServiceContainer,
) -> None:
    """
    Register every lifecycle-managed module.
    """

    register_memory(
        engine=engine,
        container=container,
    )

    register_voice(
        engine=engine,
        container=container,
    )

    register_proactive(
        engine=engine,
        container=container,
    )

    register_hologram(
        engine=engine,
        container=container,
    )
