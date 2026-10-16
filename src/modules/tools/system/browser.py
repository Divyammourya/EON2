"""
Browser Tool.

Opens URLs using the system's default web browser.
"""

from __future__ import annotations

import webbrowser

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult


class BrowserTool(Tool):
    """Tool to open a URL in the default browser."""

    @property
    def name(self) -> str:
        return "browser"

    def execute(self, url: str) -> ToolResult:
        try:
            target = url.strip()

            if not target:
                return ToolResult(
                    success=False,
                    message="No URL was provided.",
                )

            if "://" not in target:
                target = f"https://{target}"

            opened = webbrowser.open(target)

            if not opened:
                return ToolResult(
                    success=False,
                    message=f"Unable to open '{url}'.",
                )

            return ToolResult(
                success=True,
                message=f"Opened '{target}' in the default browser.",
            )

        except Exception as error:
            return ToolResult(
                success=False,
                message=str(error),
            )
