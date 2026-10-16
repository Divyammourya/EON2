"""
Resource Resolver.

Determines what type of resource a user is requesting.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.modules.tools.launcher.service import LauncherService

from .models import Resource, ResourceType


# Matches a bare Windows drive letter, e.g. "c:", "c:\", "d:/"
_DRIVE_PATTERN = re.compile(r"^[a-zA-Z]:[\\/]?$")


class ResourceResolver:

    def __init__(
        self,
        launcher: LauncherService,
        folder_names: set[str] | None = None,
        url_names: set[str] | None = None,
    ) -> None:
        self.launcher = launcher

        # Default fallbacks match FolderLauncher/UrlLauncher's built-in
        # sites, but callers (e.g. ResourceLauncher) should pass the
        # actual `known_names` from those launchers so this never
        # drifts out of sync as new folders/sites are added.
        self._folders = folder_names or {
            "desktop",
            "documents",
            "downloads",
            "pictures",
            "music",
            "videos",
            "home",
        }

        self._urls = url_names or {
            "google",
            "youtube",
            "github",
            "chatgpt",
            "gmail",
            "reddit",
            "stackoverflow",
        }

    def resolve(self, query: str) -> Resource:

        raw = query.strip()
        query = raw.lower()

        # Folder (well-known name)
        if query in self._folders:
            return Resource(
                type=ResourceType.FOLDER,
                value=query,
            )

        # URL (well-known name)
        if query in self._urls:
            return Resource(
                type=ResourceType.URL,
                value=query,
            )

        # Drive (e.g. "C:", "D:\")
        if _DRIVE_PATTERN.match(raw):
            return Resource(
                type=ResourceType.DRIVE,
                value=raw,
            )

        # File or Folder (raw filesystem path)
        path = Path(raw).expanduser()

        if path.exists():
            if path.is_file():
                return Resource(
                    type=ResourceType.FILE,
                    value=raw,
                )

            if path.is_dir():
                return Resource(
                    type=ResourceType.FOLDER,
                    value=raw,
                )

        # A query that looks like a file (has a real extension) but
        # doesn't exist yet is still routed to FILE so the launcher
        # can report a proper "not found" message instead of falling
        # through to application resolution.
        if path.suffix and len(path.suffix) <= 6:
            return Resource(
                type=ResourceType.FILE,
                value=raw,
            )

        # Application
        application = self.launcher.resolve(query)

        if application is not None:
            return Resource(
                type=ResourceType.APPLICATION,
                value=query,
            )

        return Resource(
            type=ResourceType.UNKNOWN,
            value=query,
        )
