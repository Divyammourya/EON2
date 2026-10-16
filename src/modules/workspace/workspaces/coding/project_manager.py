"""
Project manager for the Coding Workspace.

Responsible for managing the lifecycle of the currently opened project.

This class intentionally knows nothing about editors, terminals, Git,
or AI. It simply tracks which project is currently open.
"""

from __future__ import annotations

from pathlib import Path

from .exceptions import ProjectAlreadyOpenError


class ProjectManager:
    """
    Manages the currently opened coding project.
    """

    def __init__(self) -> None:
        self._project_root: Path | None = None

    def open_project(self, path: str | Path) -> None:
        """
        Open a project.

        Args:
            path:
                Path to the project directory.

        Raises:
            FileNotFoundError:
                If the directory does not exist.

            NotADirectoryError:
                If the path is not a directory.
        """

        if self.has_project():
            raise ProjectAlreadyOpenError(
                "A project is already open."
            )

        project = Path(path).expanduser().resolve()

        if not project.exists():
            raise FileNotFoundError(project)

        if not project.is_dir():
            raise NotADirectoryError(project)

        self._project_root = project

    def close_project(self) -> None:
        """
        Close the current project.
        """

        self._project_root = None

    @property
    def project_root(self) -> Path | None:
        """
        Return the current project directory.
        """

        return self._project_root

    def has_project(self) -> bool:
        """
        Return True if a project is currently open.
        """

        return self._project_root is not None
