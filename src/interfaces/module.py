"""
Base interface for all EON modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Module(ABC):
    """Base class for every EON module."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the module name."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the module."""

    @abstractmethod
    def start(self) -> None:
        """Start the module."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the module."""

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the module."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return module health."""
