

"""
Tool Manager.
"""

from __future__ import annotations

from src.modules.tools.launcher.service import LauncherService
from src.modules.tools.models import ToolResult


class ToolManager:
    """
    High-level entry point for EON tools.
    """

    def __init__(self) -> None:
        self.launcher = LauncherService()

    def execute(
        self,
        tool_name: str,
    ) -> ToolResult:

        return self.launcher.launch(tool_name)
