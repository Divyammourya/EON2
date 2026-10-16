class ProjectError(Exception):
    """Base exception for Coding Workspace project errors."""


class NoProjectOpenError(ProjectError):
    """Raised when an operation requires an open project."""


class ProjectAlreadyOpenError(ProjectError):
    """Raised when attempting to open a second project."""


class FileOutsideProjectError(ProjectError):
    """Raised when a file operation targets a path outside the project."""


class FileNotFoundInProjectError(ProjectError):
    """Raised when a project-relative file does not exist."""
