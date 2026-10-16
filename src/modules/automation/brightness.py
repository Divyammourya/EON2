"""
Brightness Tool.

Controls display brightness via the `screen-brightness-control`
library. That library already handles the messy part of this problem
on Windows — trying WMI's `WmiMonitorBrightnessMethods` where it's
supported, falling back to DDC/CI for monitors that only support
that, and working around a number of per-vendor quirks neither
approach handles cleanly on its own. Requires the
`screen-brightness-control` package (pip install
screen-brightness-control) — see requirements.txt.

Not every display supports software brightness control at all; that
shows up here as a normal "not supported" result rather than an
error.
"""

from __future__ import annotations

import re

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

_PERCENT_PATTERN = re.compile(r"(\d{1,3})\s*%?")
_BRIGHTNESS_STEP = 10


class BrightnessTool(Tool):
    """Tool to get/set the primary display's brightness."""

    @property
    def name(self) -> str:
        return "brightness"

    def execute(self, command: str = "") -> ToolResult:
        try:
            import screen_brightness_control as sbc
        except ImportError as error:
            return ToolResult(
                success=False,
                message=(
                    "Brightness control requires the "
                    "'screen-brightness-control' package "
                    f"(pip install screen-brightness-control). Error: {error}"
                ),
            )

        text = (command or "").strip().lower()

        try:
            levels = sbc.get_brightness()
        except Exception as error:
            return ToolResult(
                success=False,
                message=(
                    "This display doesn't support software brightness "
                    f"control. Error: {type(error).__name__}: {error}"
                ),
            )

        if not levels:
            return ToolResult(
                success=False,
                message="This display doesn't support software brightness control.",
            )

        current = levels[0]

        if not text or "status" in text or "what" in text:
            return ToolResult(success=True, message=f"Brightness is at {current}%.")

        def _apply(requested: int) -> int:
            level = max(0, min(100, requested))
            sbc.set_brightness(level)
            return level

        try:
            match = _PERCENT_PATTERN.search(text)

            if match and ("set" in text or "%" in text or text.strip(" %").isdigit()):
                requested = max(0, min(100, int(match.group(1))))
                applied = _apply(requested)
                return ToolResult(success=True, message=f"Brightness set to {applied}%.")

            if any(word in text for word in ("up", "increase", "brighten")):
                requested = min(100, current + _BRIGHTNESS_STEP)
                applied = _apply(requested)
                return ToolResult(
                    success=True, message=f"Brightness increased to {applied}%."
                )

            if any(word in text for word in ("down", "decrease", "dim")):
                requested = max(0, current - _BRIGHTNESS_STEP)
                applied = _apply(requested)
                return ToolResult(
                    success=True, message=f"Brightness decreased to {applied}%."
                )

            return ToolResult(
                success=False,
                message=f"I didn't understand the brightness command: '{command}'.",
            )

        except Exception as error:
            return ToolResult(
                success=False,
                message=(
                    "Failed to change brightness. "
                    f"Error: {type(error).__name__}: {error}"
                ),
            )
