"""
Recall models.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MemoryMatch:
    """
    A recalled memory.
    """

    content: str

    score: float = 1.0


@dataclass(slots=True)
class RecallResult:
    """
    Result returned by Recall.
    """

    memories: list[MemoryMatch] = field(default_factory=list)

    @property
    def has_memories(self) -> bool:
        return len(self.memories) > 0
