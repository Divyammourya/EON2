"""
Application Bootstrap.

Loads the application registry from disk,
or builds it if it doesn't exist.
"""

from __future__ import annotations

from pathlib import Path

from src.modules.tools.launcher.builder import ApplicationBuilder
from src.modules.tools.launcher.registry import ApplicationRegistry
from src.modules.tools.launcher.repository import ApplicationRepository


REGISTRY_PATH = (
    Path(__file__).parent / "registry.json"
)


def build_registry() -> ApplicationRegistry:

    repository = ApplicationRepository(REGISTRY_PATH)

    registry = ApplicationRegistry()

    if repository.exists():

        for app in repository.load():
            registry.register(app)

        return registry

    builder = ApplicationBuilder()

    registry = builder.build()

    repository.save(registry.list())

    return registry
