"""
Windows shortcut resolver.

Resolves .lnk shortcut files into their executable targets.
"""

from __future__ import annotations

from pathlib import Path

import win32com.client


class ShortcutResolver:
    """
    Resolves Windows .lnk shortcut files.
    """

    def __init__(self) -> None:
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
