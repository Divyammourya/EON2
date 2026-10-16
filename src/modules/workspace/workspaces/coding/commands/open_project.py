from __future__ import annotations

from .base import CodingCommand


class OpenProjectCommand(CodingCommand):

    def __init__(
        self,
        project_manager,
        path: str,
    ):
        self.project_manager = project_manager
        self.path = path

    def execute(self):

        self.project_manager.open_project(
            self.path,
        )

        return {
            "success": True,
            "project": str(
                self.project_manager.project_root,
            ),
        }
