"""
Search manager for the Coding Workspace.

Provides project-wide search capabilities.

This class intentionally knows nothing about AI, editors, terminals,
or Git. It is responsible only for locating files and searching text
within the current project.
"""

from __future__ import annotations

from pathlib import Path

from .project_manager import ProjectManager
from .exceptions import NoProjectOpenError


class SearchManager:
    """
    Performs project-wide searches.
    """

    def __init__(
        self,
        project_manager: ProjectManager,
    ) -> None:
        self._project_manager = project_manager

    @property
    def project_root(self) -> Path:
        """
        Return the current project root.
        """

        root = self._project_manager.project_root

        if root is None:
            raise NoProjectOpenError(
                "No project is currently open."
            )

        return root

    def find_files(
        self,
        pattern: str,
    ) -> list[Path]:
        """
        Find files matching a glob pattern.

        Example:
            *.py
            **/*.md
            src/**/*.ts
        """

        return sorted(
            self.project_root.glob(pattern)
        )

    def find_by_name(
        self,
        name: str,
    ) -> list[Path]:
        """
        Find files by filename.
        """

        matches: list[Path] = []

        for path in self.project_root.rglob("*"):
            if path.is_file() and path.name == name:
                matches.append(path)

        return sorted(matches)

    def search_text(
        self,
        text: str,
    ) -> list[Path]:
        """
        Return files containing the given text.
        """

        matches: list[Path] = []

        for path in self.project_root.rglob("*"):
            if not path.is_file():
                continue

            try:
                content = path.read_text(
                    encoding="utf-8",
                )
            except Exception:
                continue

            if text in content:
                matches.append(path)

        return sorted(matches)
