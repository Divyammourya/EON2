"""
Base class for all EON tools.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Tool(ABC):
    """Abstract base class for tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        ...

    @abstractmethod
    def execute(self, *args, **kwargs):
        """Execute the tool."""
        ...
