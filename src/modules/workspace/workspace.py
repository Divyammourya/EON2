"""
Workspace base class.

Defines the abstract contract that every EON workspace implementation must
fulfill. A Workspace represents a single, self-contained context of work
(for example: a coding workspace, a research workspace, a communications
workspace, etc.).

This module intentionally knows nothing about *how* workspaces are created,
tracked, switched between, or persisted at the system level — that is the
responsibility of higher-level components such as a workspace manager or
registry. Likewise, this module has no awareness of UI rendering, terminal
sessions, Git, AI providers, or the file system. A Workspace only describes
its own lifecycle and its own state; it does not reach outside itself.

Concrete subclasses are responsible for implementing the actual behavior
behind each lifecycle method.
"""

from abc import ABC, abstractmethod
from src.modules.intent.models import Intent
from .models import (
    WorkspaceMetadata,
    WorkspaceState,
    WorkspaceSession,
)


class Workspace(ABC):
    """
    Abstract base class representing a single EON workspace.

    A Workspace is a self-contained unit of context and state. It does not
    know about other workspaces, how it was created, or what created it.
    Subclasses implement the concrete behavior for each lifecycle stage.

    Subclasses should call super().__init__() before performing their own
    initialization so that the common workspace models are created correctly.
    """
    def __init__(self) -> None:
        """
        Initialize the common workspace data.

        Concrete workspaces should populate these objects during their own
        initialization rather than replacing them.
        """
        self._metadata = WorkspaceMetadata(
            id="",
            name="",
            description="",
            icon="",
            category="",
            version="1.0.0",
        )

        self._state = WorkspaceState()

        self._session: WorkspaceSession | None = None

    @property
    def metadata(self) -> WorkspaceMetadata:
        """
        Read-only access to the workspace's descriptive metadata.

        Returns:
            The WorkspaceMetadata stored in self._metadata.
        """
        return self._metadata

    @property
    def state(self) -> WorkspaceState:
        """
        Read-only access to the workspace's current runtime state.

        Returns:
            The WorkspaceState stored in self._state.
        """
        return self._state

    @property
    def session(self) -> WorkspaceSession | None:
        """
        Read-only access to the workspace's current session data, if any.

        Returns:
            The WorkspaceSession stored in self._session, or None if the
            workspace has no session data currently held.
        """
        return self._session

    @abstractmethod
    def initialize(self) -> None:
        """
        Prepare the workspace for first-time use.

        Called once when the workspace is first created, before it has ever
        been opened. Intended for one-time setup that should not be repeated
        on subsequent open/close cycles.
        """
        raise NotImplementedError

    @abstractmethod
    def shutdown(self) -> None:
        """
        Permanently tear down the workspace.

        Called when the workspace is being retired for good (not merely
        closed). Intended for final cleanup that should only ever happen
        once, mirroring `initialize()`.
        """
        raise NotImplementedError

    @abstractmethod
    def open(self) -> None:
        """
        Open the workspace, making it available for use.

        May be called repeatedly across the workspace's lifetime, unlike
        `initialize()`. Represents the workspace becoming ready to be
        interacted with.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """
        Close the workspace, making it unavailable for use.

        The counterpart to `open()`. The workspace is not destroyed and may
        be opened again later.
        """
        raise NotImplementedError

    @abstractmethod
    def activate(self) -> None:
        """
        Bring the workspace into the foreground as the current context.

        An activated workspace is the one currently receiving focus. A
        workspace may be open without being active.
        """
        raise NotImplementedError

    @abstractmethod
    def deactivate(self) -> None:
        """
        Move the workspace out of the foreground.

        The counterpart to `activate()`. The workspace remains open but is
        no longer the current context.
        """
        raise NotImplementedError

    @abstractmethod
    def save_session(self) -> WorkspaceSession:
        """
        Capture the current workspace session.

        Returns:
            A WorkspaceSession containing all information required to restore
            the workspace at a later time.
        """
        raise NotImplementedError

    @abstractmethod
    def restore_session(self, session: WorkspaceSession) -> None:
        """
        Restore a previously saved workspace session.

        Args:
            session:
                The WorkspaceSession produced by save_session().
        """
        raise NotImplementedError

    @abstractmethod
    def get_state(self) -> WorkspaceState:
        """
        Return the current runtime state of the workspace.

        Returns:
            WorkspaceState describing the workspace's live status.
        """
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self) -> WorkspaceMetadata:
        """
        Return descriptive information about the workspace.

        Returns:
            WorkspaceMetadata describing this workspace.
        """
        raise NotImplementedError

    @abstractmethod
    def can_handle(self, intent: Intent) -> bool:
        """
        Determine whether this workspace is capable of handling a given intent.

        Args:
            intent: The intent under consideration.

        Returns:
            True if this workspace can handle the intent, False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def handle_intent(self, intent: Intent) -> object:
        """
        Handle a given intent.

        Args:
            intent: The intent to handle. Callers should typically confirm
                the workspace `can_handle()` the intent before calling this.

        Returns:
            The result of handling the intent, as defined by the concrete
            workspace implementation.
        """
        raise NotImplementedError
