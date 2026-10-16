

"""
Launcher Service.

Public interface for launching desktop applications.
"""

from __future__ import annotations

from src.modules.tools.launcher.builder import ApplicationBuilder
from src.modules.tools.launcher.cache import ApplicationCache
from src.modules.tools.launcher.session import ApplicationSession
from src.modules.tools.models import ToolResult


class LauncherService:

    def __init__(self) -> None:
        self.session = ApplicationSession()
        self.cache = ApplicationCache()
        self.builder = ApplicationBuilder()

        registry = self.cache.load()

        if registry is None:
            registry = self.builder.build()
            self.cache.save(registry)

        self.registry = registry

    def refresh(self) -> None:
        """
        Rebuild the application cache.
        """

        registry = self.builder.build()

        self.cache.save(registry)

        self.registry = registry

    def resolve(self, query: str):
        """
        Resolve an application without launching it.
        """
        return self.session.resolver.resolve(query)

    def launch(self, query: str) -> ToolResult:

        application = self.resolve(query)

        if application is None:
            return ToolResult(
                success=False,
                message=f"Application '{query}' not found.",
            )

        success = self.session.launch(query)

        if success:
            return ToolResult(
                success=True,
                message=f"{application.name} launched successfully.",
            )

        return ToolResult(
            success=False,
            message=f"Failed to launch '{application.name}'.",
        )
