"""
Application Registry.

Stores and retrieves registered desktop applications.
"""

from __future__ import annotations

from typing import Iterator

from src.modules.tools.launcher.models import (
    Application,
    ApplicationAlreadyExistsError,
    ApplicationNotFoundError,
)


class ApplicationRegistry:
    """
    Stores launchable desktop applications.
    """

    def __init__(self) -> None:
        self._applications: dict[str, Application] = {}

    @staticmethod
    def _normalize(name: str) -> str:
        return name.strip().lower()

    def register(self, application: Application) -> None:
        """
        Register a new application.
        """

        key = self._normalize(application.name)

        if key in self._applications:
            raise ApplicationAlreadyExistsError(
                f"Application '{application.name}' is already registered."
            )

        self._applications[key] = application

    def unregister(self, name: str) -> None:
        """
        Remove an application.
        """

        key = self._normalize(name)

        if key not in self._applications:
            raise ApplicationNotFoundError(name)

        del self._applications[key]

    def get(self, name: str) -> Application:
        """
        Retrieve an application by name.
        """

        key = self._normalize(name)

        try:
            return self._applications[key]

        except KeyError as error:
            raise ApplicationNotFoundError(name) from error

    def find(self, query: str) -> list[Application]:
        """
        Search registered applications.
        """

        return [
            app
            for app in self._applications.values()
            if app.matches(query)
        ]

    def list(self) -> list[Application]:
        """
        Return every registered application.
        """

        return list(self._applications.values())

    def __contains__(self, name: str) -> bool:
        return self._normalize(name) in self._applications

    def __len__(self) -> int:
        return len(self._applications)

    def __iter__(self) -> Iterator[Application]:
        return iter(self._applications.values())
