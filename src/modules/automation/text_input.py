"""
Text Input Tool.

Types text into whatever window currently has focus, by placing the
text on the clipboard and simulating Ctrl+V, rather than simulating
individual keystrokes. This ensures unicode text and punctuation
paste correctly regardless of keyboard layout. The user's previous
clipboard contents are restored afterward.
"""

from __future__ import annotations

import time

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

_PASTE_SETTLE_SECONDS = 0.1
_KEY_HOLD_SECONDS = 0.05


class TypeTextTool(Tool):
    """Tool to type/paste text into the focused window."""

    @property
    def name(self) -> str:
        return "type_text"

    def _get_clipboard_text(self) -> str | None:
        import win32clipboard

        win32clipboard.OpenClipboard()

        try:
            if win32clipboard.IsClipboardFormatAvailable(
                win32clipboard.CF_UNICODETEXT
            ):
                return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            return None
        finally:
            win32clipboard.CloseClipboard()

    def _set_clipboard_text(self, text: str) -> None:
        import win32clipboard
        import win32con

        win32clipboard.OpenClipboard()

        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()

    def execute(self, text: str = "") -> ToolResult:
        try:
            content = (text or "").strip()

            if not content:
                return ToolResult(
                    success=False, message="No text was provided to type."
                )

            import win32api
            import win32con

            previous = self._get_clipboard_text()

            self._set_clipboard_text(content)

            # Simulate Ctrl+V into whatever window currently has focus.
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(ord("V"), 0, 0, 0)
            time.sleep(_KEY_HOLD_SECONDS)
            win32api.keybd_event(ord("V"), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

            time.sleep(_PASTE_SETTLE_SECONDS)

            if previous is not None:
                self._set_clipboard_text(previous)

            return ToolResult(success=True, message=f"Typed: {content}")

        except Exception as error:
            return ToolResult(success=False, message=str(error))
