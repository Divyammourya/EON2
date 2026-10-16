"""
Clipboard Tool.

Reads from and writes plain text to the Windows clipboard, via
pywin32 (already a project dependency), so no new package is needed
just for clipboard access.
"""

from __future__ import annotations

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

_MAX_PREVIEW_CHARS = 500


class ClipboardTool(Tool):
    """Tool to read or write plain text on the system clipboard."""

    @property
    def name(self) -> str:
        return "clipboard"

    def execute(self, text: str = "") -> ToolResult:
        """Reads the clipboard, or writes ``text`` to it if provided.

        Args:
            text: Text to copy to the clipboard. If empty, the current
                clipboard contents are read instead.
        """
        stripped = (text or "").strip()

        if stripped:
            return self._write(stripped)

        return self._read()

    def _read(self) -> ToolResult:
        try:
            import win32clipboard

            win32clipboard.OpenClipboard()

            try:
                if not win32clipboard.IsClipboardFormatAvailable(
                    win32clipboard.CF_UNICODETEXT
                ):
                    return ToolResult(
                        success=False,
                        message="The clipboard doesn't currently contain text.",
                    )

                contents = win32clipboard.GetClipboardData(
                    win32clipboard.CF_UNICODETEXT
                )
            finally:
                win32clipboard.CloseClipboard()

            contents = (contents or "").strip()

            if not contents:
                return ToolResult(success=False, message="The clipboard is empty.")

            preview = (
                contents
                if len(contents) <= _MAX_PREVIEW_CHARS
                else contents[:_MAX_PREVIEW_CHARS] + "..."
            )

            return ToolResult(success=True, message=preview)

        except Exception as error:
            return ToolResult(success=False, message=str(error))

    def _write(self, text: str) -> ToolResult:
        try:
            import win32clipboard
            import win32con

            win32clipboard.OpenClipboard()

            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()

            return ToolResult(success=True, message="Copied to the clipboard.")

        except Exception as error:
            return ToolResult(success=False, message=str(error))
