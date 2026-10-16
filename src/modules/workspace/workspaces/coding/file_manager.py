"""
File manager for the Coding Workspace.

Responsible for performing file operations within the currently opened
project.

All paths are interpreted relative to the project root unless otherwise
specified.
"""

from __future__ import annotations

from pathlib import Path

from .exceptions import (
    FileNotFoundInProjectError,
    FileOutsideProjectError,
    NoProjectOpenError,
)
from .project_manager import ProjectManager


class FileManager:
    """
    Performs file operations inside the currently opened project.
    """

    def __init__(self, project_manager: ProjectManager) -> None:
        self._project_manager = project_manager

    def resolve_path(self, path: str) -> Path:
        """
        Resolve a project-relative path to an absolute path.

        Raises:
            NoProjectOpenError:
                If no project is currently open.

            FileOutsideProjectError:
                If the resolved path escapes the project root.
        """

        if not self._project_manager.has_project():
            raise NoProjectOpenError(
                "No project is currently open."
            )

        project_root = self._project_manager.project_root
        assert project_root is not None

        resolved = (project_root / path).resolve()

        try:
            resolved.relative_to(project_root)
        except ValueError:
            raise FileOutsideProjectError(
                f"'{path}' is outside the current project."
            ) from None

        return resolved

    def exists(self, path: str) -> bool:
        """
        Return True if a project-relative path exists.
        """

        return self.resolve_path(path).exists()

    def read_file(self, path: str) -> str:
        """
        Read a UTF-8 text file from the project.
        """

        file_path = self.resolve_path(path)

        if not file_path.exists():
            raise FileNotFoundInProjectError(path)

        return file_path.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> None:
        """
        Write UTF-8 text to a project file.
        """

        file_path = self.resolve_path(path)

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path.write_text(
            content,
            encoding="utf-8",
        )

    def create_file(self, path: str) -> None:
        """
        Create an empty file if it does not already exist.
        """

        self.write_file(path, "")

    def create_directory(self, path: str) -> None:
        """
        Create a directory (and any missing parent directories)
        inside the project. No-op if it already exists.
        """

        directory = self.resolve_path(path)

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def delete_file(self, path: str) -> None:
        """
        Delete a project file.
        """

        file_path = self.resolve_path(path)

        if not file_path.exists():
            raise FileNotFoundInProjectError(path)

        file_path.unlink()

    def list_directory(
        self,
        path: str = "",
    ) -> list[Path]:
        """
        Return the contents of a project directory.
        """

        directory = self.resolve_path(path)

        if not directory.is_dir():
            raise NotADirectoryError(directory)

        return sorted(directory.iterdir())
