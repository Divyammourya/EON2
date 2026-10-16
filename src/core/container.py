"""
Service Container for EON.

Provides a central registry for shared application services.
"""

from __future__ import annotations

from typing import Any

from src.core.logger import get_logger

logger = get_logger("Container")


class ServiceContainer:
    """Central registry for shared services."""

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

        logger.info("Service Container initialized.")

    def register(self, name: str, service: Any) -> None:
        """
        Register a service.

        Args:
            name: Service name.
            service: Service instance.
        """

        if name in self._services:
            raise ValueError(f"Service '{name}' is already registered.")

        self._services[name] = service

        logger.info("Registered service: %s", name)

    def get(self, name: str) -> Any:
        """
        Retrieve a registered service.

        Args:
            name: Service name.

        Returns:
            The registered service instance.
        """

        if name not in self._services:
            raise KeyError(f"Unknown service '{name}'.")

        return self._services[name]

    def __contains__(self, name: str) -> bool:
        """Check whether a service is registered."""

        return name in self._services

    def list_services(self) -> list[str]:
        """Return all registered service names."""

        return sorted(self._services.keys())
