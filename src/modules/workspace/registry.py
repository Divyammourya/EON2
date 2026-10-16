"""
Workspace registry.

Provides a simple, storage-only registry for `Workspace` instances, keyed
by workspace ID. The registry's sole responsibility is bookkeeping — it
does not initialize, open, activate, switch between, or otherwise manage
the lifecycle of the workspaces it holds. Lifecycle orchestration belongs
to a higher-level component (such as a workspace manager); this registry
is purely a lookup table.
"""

from typing import List

from .workspace import Workspace
from .exceptions import WorkspaceAlreadyRegisteredError, WorkspaceNotFoundError



class WorkspaceRegistry:
    """
    Storage-only registry of `Workspace` instances, keyed by workspace ID.

    Responsible strictly for registering, retrieving, and removing
    workspace instances. Has no awareness of workspace lifecycle
    (initialization, opening, activation, switching, etc.) and performs
    no such operations on the workspaces it stores.
    """

    def __init__(self) -> None:
        """Initialize an empty workspace registry."""
        self._workspaces: dict[str, Workspace] = {}

    def register(self, workspace: Workspace) -> None:
        """
        Register a workspace instance.

        The workspace's identifier is obtained from
        `workspace.get_metadata().id`.

        Args:
            workspace: The workspace instance to register.

        Raises:
            WorkspaceAlreadyRegisteredError: If a workspace with the same
                ID is already registered.
        """
        workspace_id = workspace.metadata.id
        if workspace_id in self._workspaces:
            raise WorkspaceAlreadyRegisteredError(
                f"Workspace '{workspace_id}' is already registered."
            )
        self._workspaces[workspace_id] = workspace

    def unregister(self, workspace_id: str) -> None:
        """
        Remove a workspace from the registry.

        Args:
            workspace_id: The identifier of the workspace to remove.

        Raises:
            WorkspaceNotFoundError: If no workspace with the given ID is
                registered.
        """
        if workspace_id not in self._workspaces:
            raise WorkspaceNotFoundError(
                f"Workspace '{workspace_id}' is not registered."
            )
        del self._workspaces[workspace_id]

    def get(self, workspace_id: str) -> Workspace:
        """
        Retrieve a registered workspace by its identifier.

        Args:
            workspace_id: The identifier of the workspace to retrieve.

        Returns:
            The registered `Workspace` instance.

        Raises:
            WorkspaceNotFoundError: If no workspace with the given ID is
                registered.
        """
        if workspace_id not in self._workspaces:
            raise WorkspaceNotFoundError(
                f"Workspace '{workspace_id}' is not registered."
            )
        return self._workspaces[workspace_id]

    def exists(self, workspace_id: str) -> bool:
        """
        Check whether a workspace with the given identifier is registered.

        Args:
            workspace_id: The identifier to check.

        Returns:
            True if a workspace with that ID is registered, False otherwise.
        """
        return workspace_id in self._workspaces

    def list_workspaces(self) -> List[Workspace]:
        """
        List all registered workspaces.

        Returns:
            A list of all currently registered `Workspace` instances, in
            no guaranteed order.
        """
        return list(self._workspaces.values())

    def count(self) -> int:
        """
        Count the number of registered workspaces.

        Returns:
            The total number of workspaces currently registered.
        """
        return len(self._workspaces)

    def clear(self) -> None:
        """
        Remove all registered workspaces.

        Does not perform any lifecycle teardown on the removed workspaces;
        it simply empties the registry's internal storage.
        """
        self._workspaces.clear()
