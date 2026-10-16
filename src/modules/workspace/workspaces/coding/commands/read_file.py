from __future__ import annotations

from .base import CodingCommand


class ReadFileCommand(CodingCommand):

    def __init__(
        self,
        file_manager,
        editor,
        path: str,
    ):
        self.file_manager = file_manager
        self.editor = editor
        self.path = path

    def execute(self):

        absolute = self.file_manager.resolve_path(
            self.path,
        )

        content = self.file_manager.read_file(
            self.path,
        )

        self.editor.open_file(
            absolute,
        )

        return {
            "path": str(absolute),
            "content": content,
        }
