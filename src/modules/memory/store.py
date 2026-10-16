"""
Memory Store Interface.

Defines the storage contract for all memory backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.modules.memory.models import (
    MemoryEntry,
    MemoryQuery,
    MemorySearchResult,
)

from uuid import UUID

class MemoryStore(ABC):
    """
    Abstract base class for memory storage backends.

    Every memory backend must implement this interface.
    """

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the storage backend.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """
        Shutdown the storage backend.
        """

    @abstractmethod
    def save(
        self,
        memory: MemoryEntry,
    ) -> None:
        """
        Persist a memory entry.
        """

    @abstractmethod
    def update(
        self,
        memory: MemoryEntry,
    ) -> None:
        """
        Update an existing memory.
        """

    @abstractmethod
    def delete(
        self,
        memory_id: UUID,
    ) -> None:
        """
        Delete a memory entry.
        """

    @abstractmethod
    def get(
        self,
        memory_id: UUID,
    ) -> MemoryEntry | None:
        """
        Retrieve a memory by its identifier.
        """

    @abstractmethod
    def search(
        self,
        query: MemoryQuery,
    ) -> list[MemorySearchResult]:
        """
        Search for matching memories.
        """

    @abstractmethod
    def clear(self) -> None:
        """
        Remove every stored memory.
        """

    @abstractmethod
    def health_check(self) -> bool:
        """
        Return whether the backend is healthy.
        """
    @abstractmethod
    def exists(
        self,
        content: str,
        threshold: float,
    ) -> bool:
        """
        Returns True if a similar memory already exists.
        """

    @abstractmethod
    def get_learned_phrase(
        self,
        raw_phrase: str,
    ) -> tuple[str, str] | None:
        """
        Look up a learned phrase -> (intent_type, target) mapping.

        Returns ``None`` if no mapping is stored for this phrase.
        """

    @abstractmethod
    def set_learned_phrase(
        self,
        raw_phrase: str,
        intent_type: str,
        target: str,
    ) -> None:
        """
        Persist a phrase -> (intent_type, target) mapping.
        """
