

"""
Application scanner.

Responsible for discovering launchable desktop applications.
"""

from __future__ import annotations

import os
from pathlib import Path

from src.modules.tools.launcher.models import Application


class ApplicationScanner:
    """
    Scans common Windows application directories.
    """

    SEARCH_DIRS = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("LOCALAPPDATA", "")),
    ]

    def scan(self) -> list[Application]:
        """
        Scan common installation folders for executable files.
        """

        applications: list[Application] = []
        seen: set[str] = set()

        for directory in self.SEARCH_DIRS:

            if not directory.exists():
                continue

            for exe in directory.rglob("*.exe"):

                name = exe.stem.lower()

                if name in seen:
                    continue

                seen.add(name)

                applications.append(
                    Application(
                        name=name,
                        path=str(exe),
                    )
                )

        return applications
