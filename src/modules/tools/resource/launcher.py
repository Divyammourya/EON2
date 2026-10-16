"""
Unified Resource Launcher.

Dispatches resources to the correct launcher.
"""

from __future__ import annotations

from src.modules.tools.models import ToolResult
from src.modules.tools.launcher.service import LauncherService

from src.modules.tools.resource.folder_launcher import FolderLauncher
from src.modules.tools.resource.url_launcher import UrlLauncher
from src.modules.tools.resource.file_launcher import FileLauncher

from src.modules.tools.resource.resolver import (
    ResourceResolver,
    ResourceType,
)


class ResourceLauncher:

    def __init__(self) -> None:

        self.applications = LauncherService()

        self.folders = FolderLauncher()

        self.urls = UrlLauncher()

        self.files = FileLauncher()

        self.resolver = ResourceResolver(
            self.applications,
            folder_names=self.folders.known_names,
            url_names=self.urls.known_names,
        )

    def open(self, query: str) -> ToolResult:

        resource = self.resolver.resolve(query)

        if resource.type == ResourceType.APPLICATION:
            return self.applications.launch(resource.value)

        if resource.type == ResourceType.FOLDER:

            success = self.folders.open(resource.value)

            return ToolResult(
                success=success,
                message=(
                    f"{resource.value} opened successfully."
                    if success
                    else f"Folder '{resource.value}' not found."
                ),
            )

        if resource.type == ResourceType.URL:

            success = self.urls.open(resource.value)

            return ToolResult(
                success=success,
                message=(
                    f"{resource.value} opened successfully."
                    if success
                    else f"Unable to open '{resource.value}'."
                ),
            )

        if resource.type == ResourceType.FILE:

            success = self.files.open(resource.value)

            return ToolResult(
                success=success,
                message=(
                    f"{resource.value} opened successfully."
                    if success
                    else f"File '{resource.value}' not found."
                ),
            )

        if resource.type == ResourceType.DRIVE:

            success = self.folders.open_path(resource.value)

            return ToolResult(
                success=success,
                message=(
                    f"{resource.value} opened successfully."
                    if success
                    else f"Drive '{resource.value}' not found."
                ),
            )

        return ToolResult(
            success=False,
            message=f"Unknown resource '{query}'.",
        )
