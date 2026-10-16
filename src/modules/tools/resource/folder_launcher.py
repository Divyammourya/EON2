"""
Folder Launcher.

Opens common Windows folders.
"""

from __future__ import annotations

import os
from pathlib import Path


class FolderLauncher:
    """
    Opens well-known Windows folders.
    """

    def __init__(self) -> None:

        home = Path.home()

        self._folders: dict[str, Path] = {
            "desktop": home / "Desktop",
            "documents": home / "Documents",
            "downloads": home / "Downloads",
            "pictures": home / "Pictures",
            "music": home / "Music",
            "videos": home / "Videos",
            "home": home,
        }

    @property
    def known_names(self) -> set[str]:
        """
        Names of the well-known folders this launcher can open.
        """
        return set(self._folders.keys())

    def open(self, query: str) -> bool:
        """
        Opens a folder by name.
        """

        key = query.strip().lower()

        folder = self._folders.get(key)

        if folder is None:
            return self.open_path(query)

        if not folder.exists():
            return False

        os.startfile(folder)

        return True

    def open_path(self, path: str) -> bool:
        """
        Opens an arbitrary folder or drive by path.
        """

        try:
            target = Path(path).expanduser()

            if not target.exists() or not target.is_dir():
                return False

            os.startfile(target)

            return True

        except Exception:
            return False
