"""
Domain models for the EON Application Launcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# ==========================================================
# Exceptions
# ==========================================================


class LauncherError(Exception):
    """Base launcher exception."""


class ApplicationAlreadyExistsError(LauncherError):
    """Raised when registering an application that already exists."""


class ApplicationNotFoundError(LauncherError):
    """Raised when an application cannot be found."""


# ==========================================================
# Domain Model
# ==========================================================


@dataclass(slots=True, frozen=True)
class Application:
    """
    Represents a launchable desktop application.
    """

    name: str
    path: str
    aliases: list[str] = field(default_factory=list)

    def exists(self) -> bool:
        """
        Returns True if the executable exists.
        """
        return Path(self.path).exists()

    def matches(self, query: str) -> bool:
        """
        Returns True if the query matches the application's
        name or one of its aliases.
        """
        query = query.lower().strip()

        if query == self.name.lower():
            return True

        return any(
            query == alias.lower()
            for alias in self.aliases
        )
