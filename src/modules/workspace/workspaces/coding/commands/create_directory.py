from __future__ import annotations

from ..exceptions import ProjectError
from .base import CodingCommand


class CreateDirectoryCommand(CodingCommand):
    """
    Creates a directory (and any missing parents) inside the project.

    Same error-reporting convention as CreateFileCommand: expected
    failures come back as a result dict, not a raised exception.
    """

    def __init__(
        self,
        file_manager,
        path: str,
    ):
        self.file_manager = file_manager
        self.path = path

    def execute(self):

        try:
            self.file_manager.create_directory(
                self.path,
            )
        except ProjectError as exc:
            return {
                "success": False,
                "path": self.path,
                "error": str(exc),
            }

        absolute = self.file_manager.resolve_path(
            self.path,
        )

        return {
            "success": True,
            "path": str(absolute),
        }
