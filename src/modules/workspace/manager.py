"""
Workspace manager.

Defines the `WorkspaceManager`, the component responsible for coordinating
workspace lifecycle at the system level. The manager owns a
`WorkspaceRegistry` along with a notion of which workspace is currently
active and which was active immediately before it, and it is the layer
above `Workspace` and `WorkspaceRegistry` that the rest of EON is expected
to interact with for workspace orchestration.

This module has no knowledge of AI providers, LLMs, editors, terminals,
Git, coding tools, UI rendering, the file system, or networking. It
coordinates workspace objects; it does not know what any given workspace
does internally or how it is presented.
"""

from typing import List, Optional

from src.modules.workspace.registry import WorkspaceRegistry
from src.modules.workspace.workspace import Workspace


class WorkspaceManager:
    """
    Coordinates workspace lifecycle by orchestrating a `WorkspaceRegistry`.

    The manager owns the registry of known workspaces along with the
    concept of an active workspace and a previous workspace. It does not
    implement switching, activation, deactivation, session restoration, or
    intent routing itself — those responsibilities belong to other
    components layered on top of this manager. This class is limited to
    registering, unregistering, retrieving, checking for, and listing
    workspaces, delegating all storage concerns to `WorkspaceRegistry`.
    """

    def __init__(self) -> None:
        """
        Initialize the workspace manager.

        Creates an empty `WorkspaceRegistry` and initializes the active
        and previous workspace references to None, indicating that no
        workspace has yet been made active.
        """
        self._registry: WorkspaceRegistry = WorkspaceRegistry()
        self._active_workspace: Optional[Workspace] = None
        self._previous_workspace: Optional[Workspace] = None

    def register_workspace(self, workspace: Workspace) -> None:
        """
        Register a workspace with the manager.

        Delegates storage of the workspace to the underlying
        `WorkspaceRegistry`.

        Args:
            workspace: The workspace instance to register.

        Raises:
            WorkspaceAlreadyRegisteredError: If a workspace with the same
                ID is already registered.
        """
        self._registry.register(workspace)

    def unregister_workspace(self, workspace_id: str) -> None:
        """
        Unregister a workspace from the manager.

        If the workspace being removed is currently active, it is first
        deactivated. If it is stored as the previous workspace reference,
        that reference is cleared.

        Args:
            workspace_id: The identifier of the workspace to unregister.

        Raises:
            WorkspaceNotFoundError:
                If no workspace with the given ID is registered.
        """
        if (
            self._active_workspace is not None
            and self._active_workspace.metadata.id == workspace_id
        ):
            self.deactivate_active_workspace()

        if (
            self._previous_workspace is not None
            and self._previous_workspace.metadata.id == workspace_id
        ):
            self._previous_workspace = None

        self._registry.unregister(workspace_id)

    def get_workspace(self, workspace_id: str) -> Workspace:
        """
        Retrieve a registered workspace by its identifier.

        Delegates lookup of the workspace to the underlying
        `WorkspaceRegistry`.

        Args:
            workspace_id: The identifier of the workspace to retrieve.

        Returns:
            The registered `Workspace` instance.

        Raises:
            WorkspaceNotFoundError: If no workspace with the given ID is
                registered.
        """
        return self._registry.get(workspace_id)

    def has_workspace(self, workspace_id: str) -> bool:
        """
        Check whether a workspace with the given identifier is registered.

        Delegates the check to the underlying `WorkspaceRegistry`.

        Args:
            workspace_id: The identifier to check.

        Returns:
            True if a workspace with that ID is registered, False otherwise.
        """
        return self._registry.exists(workspace_id)

    def list_workspaces(self) -> List[Workspace]:
        """
        List all workspaces registered with the manager.

        Delegates retrieval of the workspace list to the underlying
        `WorkspaceRegistry`.

        Returns:
            A list of all currently registered `Workspace` instances, in
            no guaranteed order.
        """
        return self._registry.list_workspaces()

    def activate_workspace(self, workspace_id: str) -> None:
        """
        Activate a registered workspace.

        Retrieves the workspace via `get_workspace()`. If it is already
        the active workspace, this method returns immediately without
        further action. Otherwise, if a different workspace is currently
        active, that workspace is deactivated first via its own
        `deactivate()`. The requested workspace's own `activate()` is
        then called, the current active workspace becomes the previous
        workspace, and the requested workspace becomes the new active
        workspace.

        Args:
            workspace_id: The identifier of the workspace to activate.

        Raises:
            WorkspaceNotFoundError: If no workspace with the given ID is
                registered.
        """
        workspace = self.get_workspace(workspace_id)

        if workspace is self._active_workspace:
            return

        if self._active_workspace is not None:
            self._active_workspace.deactivate()

        workspace.activate()

        self._previous_workspace = self._active_workspace
        self._active_workspace = workspace

    def deactivate_active_workspace(self) -> None:
        """
        Deactivate the currently active workspace, if any.

        If a workspace is active, its own `deactivate()` is called, it
        becomes the previous workspace, and the active workspace
        reference is cleared to None. If no workspace is currently
        active, this method does nothing.
        """
        if self._active_workspace is None:
            return

        self._active_workspace.deactivate()

        self._previous_workspace = self._active_workspace
        self._active_workspace = None

    def get_active_workspace(self) -> Optional[Workspace]:
        """
        Retrieve the currently active workspace, if any.

        Returns:
            The `Workspace` stored in `self._active_workspace`, or None
            if no workspace is currently active.
        """
        return self._active_workspace

    def get_previous_workspace(self) -> Optional[Workspace]:
        """
        Retrieve the previously active workspace, if any.

        Returns:
            The `Workspace` stored in `self._previous_workspace`, or None
            if no workspace has been active before the current one.
        """
        return self._previous_workspace

    @property
    def registry(self) -> WorkspaceRegistry:
        """
        Read-only access to the workspace registry.
        """
        return self._registry


    @property
    def active_workspace(self) -> Optional[Workspace]:
        """
        Read-only access to the currently active workspace.
        """
        return self._active_workspace


    @property
    def previous_workspace(self) -> Optional[Workspace]:
        """
        Read-only access to the previously active workspace.
        """
        return self._previous_workspace
