"""
Resource Service.

High-level service for opening folders, URLs,
files and other desktop resources.
"""

from __future__ import annotations

from src.modules.tools.models import ToolResult
from src.modules.tools.resource.folder_launcher import FolderLauncher
from src.modules.tools.resource.url_launcher import UrlLauncher

from src.modules.tools.resource.file_launcher import FileLauncher
from src.modules.tools.resource.launcher import ResourceLauncher

class ResourceService:

    def __init__(self) -> None:

        self.folders = FolderLauncher()
        self.urls = UrlLauncher()
        self.files = FileLauncher()
        self.launcher = ResourceLauncher()

    def open_folder(self, name: str) -> ToolResult:

        success = self.folders.open(name)

        if success:
            return ToolResult(
                success=True,
                message=f"{name} opened successfully.",
            )

        return ToolResult(
            success=False,
            message=f"Folder '{name}' not found.",
        )

    def open_url(self, url: str) -> ToolResult:

        success = self.urls.open(url)

        if success:
            return ToolResult(
                success=True,
                message=f"{url} opened successfully.",
            )

        return ToolResult(
            success=False,
            message=f"Unable to open '{url}'.",
        )
    def open_file(self, path: str) -> ToolResult:

        success = self.files.open(path)

        if success:
            return ToolResult(
                success=True,
                message=f"{path} opened successfully.",
            )

        return ToolResult(
            success=False,
            message=f"File '{path}' not found.",
        )
    def open(self, query: str) -> ToolResult:
        """
        Open any supported resource.
        """

        return self.launcher.open(query)
