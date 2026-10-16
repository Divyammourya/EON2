"""
VS Code Tool.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult


class VSCodeTool(Tool):
    """Tool to launch Visual Studio Code."""

    @property
    def name(self) -> str:
        return "vscode"

    def _resolve_executable(self) -> str | None:
        """
        Locate the VS Code executable without hardcoding a
        machine-specific path.
        """

        # 1. Already on PATH (most common case, all platforms).
        found = shutil.which("code")

        if found:
            return found

        # 2. Common per-user Windows install location.
        local_app_data = os.environ.get("LOCALAPPDATA")

        if local_app_data:
            candidate = (
                Path(local_app_data)
                / "Programs"
                / "Microsoft VS Code"
                / "Code.exe"
            )

            if candidate.exists():
                return str(candidate)

        return None

    def execute(self) -> ToolResult:
        try:
            executable = self._resolve_executable()

            if executable is None:
                return ToolResult(
                    success=False,
                    message="Visual Studio Code was not found on this machine.",
                )

            subprocess.Popen([executable])

            return ToolResult(
                success=True,
                message="Visual Studio Code launched successfully.",
            )

        except Exception as error:
            return ToolResult(
                success=False,
                message=str(error),
            )
