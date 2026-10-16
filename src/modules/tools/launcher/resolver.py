"""
Windows shortcut resolver.

Resolves .lnk shortcut files into their executable targets.
"""

from __future__ import annotations

from pathlib import Path

# win32com is Windows-only (pywin32). Importing it at module top level
# made *every* module under src.modules.tools unimportable on Linux/macOS
# and CI runners, because tools/launcher/__init__.py re-exports this file.
# We import it defensively and only fail if the resolver is actually used
# on a platform that can't support it.
try:
    import win32com.client
except ImportError:  # pragma: no cover - non-Windows platforms
    win32com = None  # type: ignore[assignment]


class ShortcutResolver:
    """
    Resolves Windows .lnk shortcut files.
    """

    def __init__(self) -> None:
        if win32com is None:
            raise RuntimeError(
                "ShortcutResolver requires Windows (pywin32). "
                "Install pywin32 and run on Windows to resolve .lnk shortcuts."
            )

        self._shell = win32com.client.Dispatch("WScript.Shell")

    def resolve(self, shortcut: Path) -> Path | None:
        """
        Returns the executable pointed to by a shortcut.

        Returns None if the shortcut is invalid.
        """

        try:
            link = self._shell.CreateShortCut(str(shortcut))

            target = Path(link.TargetPath)

            if target.exists():
                return target

        except Exception:
            pass

        return None
