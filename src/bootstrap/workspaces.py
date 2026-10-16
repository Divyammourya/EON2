"""
Workspace bootstrap.

Creates and registers all built-in workspaces.
"""

from src.modules.workspace.manager import WorkspaceManager
from src.modules.workspace.router import WorkspaceRouter

from src.modules.workspace.workspaces.chat.chat_workspace import (
    ChatWorkspace,
)

from src.modules.workspace.workspaces.coding.coding_workspace import (
    CodingWorkspace,
)

from src.modules.workspace.service import WorkspaceService


def create_workspace_manager() -> WorkspaceManager:
    """
    Create a fully initialized WorkspaceManager.
    """

    manager = WorkspaceManager()

    manager.register_workspace(ChatWorkspace())

    manager.register_workspace(CodingWorkspace())

    return manager


def create_workspace_router(
    manager: WorkspaceManager,
) -> WorkspaceRouter:
    """
    Create a WorkspaceRouter.
    """

    return WorkspaceRouter(manager)

def create_workspace_service(
    manager: WorkspaceManager,
    router: WorkspaceRouter,
) -> WorkspaceService:
    """
    Create the WorkspaceService.
    """

    return WorkspaceService(
        manager=manager,
        router=router,
    )
