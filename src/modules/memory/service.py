"""
Memory Service.

Public interface for interacting with EON's Memory subsystem.
"""

from __future__ import annotations

from uuid import UUID

from src.core.logger import get_logger
from src.modules.memory.models import (
    MemoryEntry,
    MemoryQuery,
    MemorySearchResult,
)
from src.modules.memory.store import MemoryStore

logger = get_logger("MemoryService")


class MemoryService:
    """
    High-level interface for the Memory subsystem.

    This class acts as the single entry point for storing,
    retrieving, updating, searching, and deleting memories.
    """

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

        logger.info("Memory Service initialized.")

    def initialize(self) -> None:
        """
        Initialize the memory backend.
        """
        self._store.initialize()

    def shutdown(self) -> None:
        """
        Shutdown the memory backend.
        """
        self._store.shutdown()

    def save(
        self,
        memory: MemoryEntry,
    ) -> None:
        """
        Save a memory.
        """
        self._store.save(memory)

    def update(
        self,
        memory: MemoryEntry,
    ) -> None:
        """
        Update an existing memory.
        """
        self._store.update(memory)

    def delete(
        self,
        memory_id: UUID,
    ) -> None:
        """
        Delete a memory.
        """
        self._store.delete(memory_id)

    def get(
        self,
        memory_id: UUID,
    ) -> MemoryEntry | None:
        """
        Retrieve a memory.
        """
        return self._store.get(memory_id)

    def search(
        self,
        query: MemoryQuery,
    ) -> list[MemorySearchResult]:
        """
        Search stored memories.
        """
        return self._store.search(query)

    def clear(self) -> None:
        """
        Remove every stored memory.
        """
        self._store.clear()

    def health_check(self) -> bool:
        """
        Return the backend health status.
        """
        return self._store.health_check()

    def exists(
        self,
        content: str,
        threshold: float = 0.95,
    ) -> bool:
        """
        Returns True if a very similar memory already exists.
        """

        return self._store.exists(content, threshold)

    def get_learned_phrase(
        self,
        raw_phrase: str,
    ) -> tuple[str, str] | None:
        """
        Look up a learned phrase -> (intent_type, target) mapping.
        """
        return self._store.get_learned_phrase(raw_phrase)

    def set_learned_phrase(
        self,
        raw_phrase: str,
        intent_type: str,
        target: str,
    ) -> None:
        """
        Persist a phrase -> (intent_type, target) mapping.
        """
        self._store.set_learned_phrase(raw_phrase, intent_type, target)
