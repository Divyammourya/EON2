class WorkspaceRegistryError(Exception):
    """Base exception for all errors raised by `WorkspaceRegistry`."""


class WorkspaceAlreadyRegisteredError(WorkspaceRegistryError):
    """Raised when attempting to register a workspace ID that already exists."""


class WorkspaceNotFoundError(WorkspaceRegistryError):
    """Raised when a requested workspace ID is not present in the registry."""

class NoWorkspaceCanHandleIntentError(Exception):
    """
    Raised when no registered workspace can handle a given intent.
    """
