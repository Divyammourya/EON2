from __future__ import annotations

from ..exceptions import ProjectError
from .base import CodingCommand


class CreateFileCommand(CodingCommand):
    """
    Creates (or overwrites) a project file with the given content.

    Mirrors the error-reporting convention already used by
    EditSymbolCommand: expected failures (no project open, path
    escapes the project) come back as a `{"success": False, ...}`
    dict rather than a raised exception, so a caller stepping
    through many of these in sequence (project scaffolding) can
    keep going and report exactly what happened to each file.
    """

    def __init__(
        self,
        file_manager,
        path: str,
        content: str = "",
    ):
        self.file_manager = file_manager
        self.path = path
        self.content = content

    def execute(self):

        try:
            self.file_manager.write_file(
                self.path,
                self.content,
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
            "bytes_written": len(self.content.encode("utf-8")),
        }
