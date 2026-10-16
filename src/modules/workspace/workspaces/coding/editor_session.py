"""
Editor session for the Coding Workspace.

Tracks the current editor state independently of the filesystem.
"""

from __future__ import annotations

from pathlib import Path


class EditorSession:
    """
    Tracks the current editor session.
    """

    def __init__(self) -> None:
        self._open_files: list[Path] = []
        self._active_file: Path | None = None

    @property
    def open_files(self) -> list[Path]:
        """
        Return all currently opened files.
        """
        return list(self._open_files)

    @property
    def active_file(self) -> Path | None:
        """
        Return the currently active file.
        """
        return self._active_file

    def open_file(self, path: Path) -> None:
        """
        Open a file in the editor.
        """

        if path not in self._open_files:
            self._open_files.append(path)

        self._active_file = path

    def close_file(self, path: Path) -> None:
        """
        Close a file.
        """

        if path in self._open_files:
            self._open_files.remove(path)

        if self._active_file == path:
            self._active_file = (
                self._open_files[-1]
                if self._open_files
                else None
            )

    def set_active_file(self, path: Path) -> None:
        """
        Make an opened file the active editor tab.
        """

        if path not in self._open_files:
            self._open_files.append(path)

        self._active_file = path

    def close_all(self) -> None:
        """
        Close every opened file.
        """

        self._open_files.clear()
        self._active_file = None
