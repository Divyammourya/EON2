"""
Screenshot Tool.

Captures the full desktop and saves it to disk, for when the user
wants a saved screenshot file rather than a spoken description of the
screen (spoken description is handled by the Vision module instead).
Uses Pillow's ImageGrab, already a project dependency.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

_DEFAULT_DIR = Path.home() / "Pictures" / "EON Screenshots"


class ScreenshotTool(Tool):
    """Tool to capture the screen to an image file."""

    @property
    def name(self) -> str:
        return "screenshot"

    def execute(self, command: str = "") -> ToolResult:
        try:
            from PIL import ImageGrab

            _DEFAULT_DIR.mkdir(parents=True, exist_ok=True)

            filename = f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
            path = _DEFAULT_DIR / filename

            image = ImageGrab.grab()
            image.save(path)

            return ToolResult(success=True, message=f"Screenshot saved to '{path}'.")

        except Exception as error:
            return ToolResult(success=False, message=str(error))
