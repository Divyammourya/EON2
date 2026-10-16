"""
Windows shortcut utilities.

Provides helper functions for discovering Start Menu shortcuts.
"""

from __future__ import annotations

import os
from pathlib import Path


class ShortcutScanner:
    """
    Finds Start Menu shortcut (.lnk) files.
    """

    START_MENU_DIRS = [
        Path(
            os.environ.get(
                "ProgramData",
                r"C:\ProgramData",
            )
        )
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs",
        Path(
            os.environ.get(
                "APPDATA",
                "",
            )
        )
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs",
    ]

    def scan(self) -> list[Path]:
        """
        Returns every .lnk file inside the Start Menu.
        """

        shortcuts: list[Path] = []

        for directory in self.START_MENU_DIRS:

            if not directory.exists():
                continue

            shortcuts.extend(directory.rglob("*.lnk"))

        return shortcuts
