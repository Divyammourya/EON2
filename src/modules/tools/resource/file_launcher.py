"""
File Launcher.

Opens files using the default Windows application.
"""

from __future__ import annotations

import os
from pathlib import Path


class FileLauncher:

    def open(self, path: str) -> bool:

        try:
            file = Path(path).expanduser()

            if not file.exists():
                return False

            os.startfile(file)

            return True

        except Exception:
            return False
