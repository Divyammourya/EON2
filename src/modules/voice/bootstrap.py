"""
Voice module bootstrap.

Responsible for registering the Voice module with the Engine.
"""

from __future__ import annotations

from src.core.engine import Engine
from src.core.container import ServiceContainer

from src.modules.voice.module import VoiceModule
from src.modules.voice.service import VoiceService


def register(
    engine: Engine,
    container: ServiceContainer,
) -> None:
    """
    Register the Voice module.
    """

    service: VoiceService = container.get("voice")

    module = VoiceModule(
        service=service,
    )

    engine.module_loader.register(module)
