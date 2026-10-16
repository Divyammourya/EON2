"""
Terminal Tool.

Runs shell commands on the local machine and opens terminal windows.
"""

from __future__ import annotations

import shlex
import subprocess

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

# Commands that should never be run from this tool, even if requested,
# because they are destructive or irreversible at the OS level.
_BLOCKED_COMMANDS = {
    "rm",
    "del",
    "format",
    "rd",
    "rmdir",
    "shutdown",
    "diskpart",
    "mkfs",
}

_DEFAULT_TIMEOUT_SECONDS = 30


class TerminalTool(Tool):
    """Tool to execute shell commands and report their output."""

    @property
    def name(self) -> str:
        return "terminal"

    def execute(
        self,
        command: str,
        timeout: int = _DEFAULT_TIMEOUT_SECONDS,
    ) -> ToolResult:
        try:
            stripped = command.strip()

            if not stripped:
                return ToolResult(
                    success=False,
                    message="No command was provided.",
                )

            parts = shlex.split(stripped, posix=False)

            if not parts:
                return ToolResult(
                    success=False,
                    message="No command was provided.",
                )

            program = parts[0].lower()

            if program in _BLOCKED_COMMANDS:
                return ToolResult(
                    success=False,
                    message=(
                        f"'{parts[0]}' is blocked from automated "
                        "execution. Run it manually if intended."
                    ),
                )

            result = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )

            output = (result.stdout or result.stderr or "").strip()

            return ToolResult(
                success=result.returncode == 0,
                message=output or f"Command exited with code {result.returncode}.",
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                message=f"Command timed out after {timeout} seconds.",
            )

        except FileNotFoundError:
            return ToolResult(
                success=False,
                message=f"Command not found: '{command}'.",
            )

        except Exception as error:
            return ToolResult(
                success=False,
                message=str(error),
            )
