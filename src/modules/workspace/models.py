"""
Workspace data models.

Plain data containers shared by every EON workspace implementation (Chat,
Developer, Creative, Automation, and any future workspace type). These
classes hold no behavior — they exist purely to describe the shape of a
workspace's identity, runtime state, and session data in a generic,
workspace-agnostic way.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class WorkspaceMetadata:
    """
    Descriptive, identifying information about a workspace.

    Represents the static facts that define what a workspace is, as
    opposed to what it is currently doing. Suitable for display in a
    workspace picker, registry listing, or settings panel.

    Attributes:
        id: Unique identifier for the workspace.
        name: Human-readable display name.
        description: Short explanation of what the workspace is for.
        icon: Identifier or path referencing the workspace's icon.
        category: Grouping label used to classify the workspace
            (e.g. "chat", "developer", "creative", "automation").
        version: Version string of the workspace implementation.
        enabled: Whether the workspace is currently available for use.
        supports_sessions: Whether the workspace can save and restore
            session data.
        supports_background: Whether the workspace can continue running
            while not active/in the foreground.
    """

    id: str
    name: str
    description: str
    icon: str
    category: str
    version: str
    enabled: bool = True
    supports_sessions: bool = True
    supports_background: bool = False


@dataclass
class WorkspaceState:
    """
    Runtime state of a workspace at a given moment in time.

    Represents transient, in-the-moment status rather than the workspace's
    identity or persisted session data.

    Attributes:
        initialized: Whether the workspace has completed its one-time setup.
        opened: Whether the workspace is currently open.
        active: Whether the workspace is currently the foreground context.
        busy: Whether the workspace is currently performing work.
        loading: Whether the workspace is currently in a loading state.
        last_activated: Timestamp of the most recent activation, or None
            if the workspace has never been activated.
        current_task: Description or identifier of the task currently being
            handled by the workspace, or None if idle.
    """

    initialized: bool = False
    opened: bool = False
    active: bool = False
    busy: bool = False
    loading: bool = False
    last_activated: Optional[datetime] = None
    current_task: Optional[str] = None


@dataclass
class WorkspaceSession:
    """
    Persisted session data for a workspace.

    A generic envelope for whatever workspace-specific data a workspace
    needs to save and later restore. The base model has no knowledge of
    what `data` contains — each workspace implementation defines and
    interprets its own schema.

    Attributes:
        workspace_id: Identifier of the workspace this session belongs to.
        created_at: Timestamp when the session was first created.
        updated_at: Timestamp when the session was last updated.
        data: Workspace-specific session payload.
    """

    workspace_id: str
    created_at: datetime
    updated_at: datetime
    data: Dict[str, Any] = field(default_factory=dict)
