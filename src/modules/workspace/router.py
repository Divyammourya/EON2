"""
Workspace router.

Responsible for selecting the most appropriate workspace for an intent.
"""

from src.modules.intent.models import Intent
from src.modules.workspace.exceptions import (
    NoWorkspaceCanHandleIntentError,
)
from src.modules.workspace.manager import WorkspaceManager
from src.modules.workspace.workspace import Workspace


class WorkspaceRouter:
    """
    Routes intents to the correct workspace.
    """

    def __init__(self, manager: WorkspaceManager) -> None:
        self._manager = manager

    def route(self, intent: Intent) -> Workspace:
        """
        Return the first workspace capable of handling the intent.

        Raises:
            NoWorkspaceCanHandleIntentError
                If no registered workspace supports the intent.
        """

        for workspace in self._manager.list_workspaces():

            if workspace.can_handle(intent):
                return workspace

        raise NoWorkspaceCanHandleIntentError(
            f"No workspace can handle intent '{intent.type.value}'."
        )
