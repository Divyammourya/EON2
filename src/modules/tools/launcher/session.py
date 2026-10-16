"""
Application Session.

Creates and owns all launcher components.
"""

from __future__ import annotations

from src.modules.tools.launcher.builder import ApplicationBuilder
from src.modules.tools.launcher.dynamic_launcher import DynamicLauncher
from src.modules.tools.launcher.resolver_engine import ApplicationResolver


class ApplicationSession:

    def __init__(self) -> None:

        builder = ApplicationBuilder()

        registry = builder.build()

        self.resolver = ApplicationResolver(registry)

        self.launcher = DynamicLauncher()
    def launch(self, query: str):

        application = self.resolver.resolve(query)

        if application is None:
            return None

        success = self.launcher.launch_application(application)

        return success
