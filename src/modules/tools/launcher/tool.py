"""
Launcher Tool.
"""

from __future__ import annotations

from src.modules.tools.base import Tool
from src.modules.tools.launcher.service import LauncherService
from src.modules.tools.models import ToolResult


class LauncherTool(Tool):

    def __init__(self) -> None:
        self.service = LauncherService()

    @property
    def name(self) -> str:
        return "launcher"

    def execute(
        self,
        query: str,
    ) -> ToolResult:

        return self.service.launch(query)
