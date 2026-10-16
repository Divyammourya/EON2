"""
Window Tool.

Manages open windows on Windows: focus/switch to, minimize, maximize,
restore, and close, matched by a case-insensitive substring of the
window's title bar text. Uses pywin32 (already a project dependency).
"""

from __future__ import annotations

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

_ACTION_WORDS = (
    "minimize",
    "maximize",
    "restore",
    "close",
    "focus",
    "switch to",
    "switch window to",
    "switch",
    "bring up",
)

_TARGET_STRIP_WORDS = (
    "minimize",
    "maximize",
    "restore",
    "close",
    "focus on",
    "focus",
    "switch window to",
    "switch to",
    "switch",
    "bring up",
    "this window",
    "the window",
    "window",
)


class WindowTool(Tool):
    """Tool to manage open windows by title."""

    @property
    def name(self) -> str:
        return "window"

    def _find_window(self, title_substring: str) -> list[tuple[int, str]]:
        import win32gui

        matches: list[tuple[int, str]] = []

        def _callback(hwnd: int, _extra: object) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return

            title = win32gui.GetWindowText(hwnd)

            if title and title_substring.lower() in title.lower():
                matches.append((hwnd, title))

        win32gui.EnumWindows(_callback, None)
        return matches

    def _active_window(self) -> tuple[int, str]:
        import win32gui

        hwnd = win32gui.GetForegroundWindow()
        return hwnd, win32gui.GetWindowText(hwnd)

    def execute(self, command: str = "") -> ToolResult:
        try:
            import win32con
            import win32gui

            text = (command or "").strip().lower()

            action = next(
                (word for word in _ACTION_WORDS if word in text),
                None,
            )

            if action is None:
                return ToolResult(
                    success=False,
                    message=f"I didn't understand the window command: '{command}'.",
                )

            target_phrase = text
            for word in _TARGET_STRIP_WORDS:
                target_phrase = target_phrase.replace(word, "")
            target_phrase = target_phrase.strip()

            if target_phrase:
                matches = self._find_window(target_phrase)

                if not matches:
                    return ToolResult(
                        success=False,
                        message=f"No open window matching '{target_phrase}' was found.",
                    )

                hwnd, title = matches[0]
            else:
                hwnd, title = self._active_window()

                if not hwnd:
                    return ToolResult(success=False, message="No active window was found.")

            if action == "minimize":
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                return ToolResult(success=True, message=f"Minimized '{title}'.")

            if action == "maximize":
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                return ToolResult(success=True, message=f"Maximized '{title}'.")

            if action == "restore":
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                return ToolResult(success=True, message=f"Restored '{title}'.")

            if action == "close":
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return ToolResult(success=True, message=f"Closed '{title}'.")

            # focus / switch to / switch window to / switch / bring up
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                # Windows sometimes refuses SetForegroundWindow if EON
                # isn't already the foreground process; the window was
                # still restored, so report partial success honestly.
                return ToolResult(
                    success=True,
                    message=(
                        f"Restored '{title}', but Windows blocked switching "
                        "focus to it automatically. Click it to bring it "
                        "fully to the front."
                    ),
                )

            return ToolResult(success=True, message=f"Switched to '{title}'.")

        except Exception as error:
            return ToolResult(success=False, message=str(error))
