"""
Workspace service.

Provides the public API for interacting with the workspace system.
"""

from __future__ import annotations

from src.modules.intent.models import Intent
from src.modules.workspace.manager import WorkspaceManager
from src.modules.workspace.router import WorkspaceRouter


class WorkspaceService:
    """
    High-level interface for routing intents to workspaces.
    """

    def __init__(
        self,
        manager: WorkspaceManager,
        router: WorkspaceRouter,
    ) -> None:
        self._manager = manager
        self._router = router

    @property
    def manager(self) -> WorkspaceManager:
        return self._manager

    @property
    def router(self) -> WorkspaceRouter:
        return self._router

    def handle_intent(self, intent: Intent):
        """
        Route an intent to the appropriate workspace.
        """

        workspace = self._router.route(intent)

        if workspace is not self._manager.active_workspace:
            self._manager.activate_workspace(
                workspace.metadata.id
            )

        return workspace.handle_intent(intent)
