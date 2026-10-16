"""
File Organizer Tool.

Moves files within a well-known folder (Downloads, Desktop, Documents,
Pictures) into extension-grouped subfolders (e.g. "images",
"documents", "archives"), so EON can tidy a cluttered folder on
request.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

_FOLDER_ALIASES = {
    "downloads": Path.home() / "Downloads",
    "desktop": Path.home() / "Desktop",
    "documents": Path.home() / "Documents",
    "pictures": Path.home() / "Pictures",
}

_EXTENSION_GROUPS = {
    "images": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"},
    "documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"},
    "spreadsheets": {".xls", ".xlsx", ".csv"},
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "installers": {".exe", ".msi"},
    "videos": {".mp4", ".mov", ".avi", ".mkv"},
    "audio": {".mp3", ".wav", ".flac", ".m4a"},
}


class FileOrganizerTool(Tool):
    """Tool to organize a well-known folder into type-based subfolders."""

    @property
    def name(self) -> str:
        return "file_organizer"

    def _resolve_folder(self, text: str) -> Path | None:
        lowered = text.lower()

        for alias, path in _FOLDER_ALIASES.items():
            if alias in lowered:
                return path

        return None

    def _group_for(self, suffix: str) -> str:
        suffix = suffix.lower()

        for group, extensions in _EXTENSION_GROUPS.items():
            if suffix in extensions:
                return group

        return "other"

    def execute(self, command: str = "") -> ToolResult:
        try:
            folder = self._resolve_folder(command or "")

            if folder is None:
                return ToolResult(
                    success=False,
                    message=(
                        "I'm not sure which folder to organize. Try naming "
                        "one of: Downloads, Desktop, Documents, Pictures."
                    ),
                )

            if not folder.exists():
                return ToolResult(success=False, message=f"'{folder}' doesn't exist.")

            moved = 0

            for item in folder.iterdir():
                if item.is_dir():
                    continue

                group = self._group_for(item.suffix)
                destination_dir = folder / group
                destination_dir.mkdir(exist_ok=True)

                destination = destination_dir / item.name

                if destination.exists():
                    continue

                shutil.move(str(item), str(destination))
                moved += 1

            return ToolResult(
                success=True,
                message=f"Organized {moved} file(s) in '{folder}' into subfolders by type.",
            )

        except Exception as error:
            return ToolResult(success=False, message=str(error))
