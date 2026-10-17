"""
Memory Models.

Core data models used throughout the Memory subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class MemoryType(Enum):
    """
    Types of memories managed by EON.
    """

    WORKING = "working"
    CONVERSATION = "conversation"
    LONG_TERM = "long_term"
    KNOWLEDGE = "knowledge"


class MemoryImportance(Enum):
    """
    Importance level of a memory.
    """

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(slots=True)
class MemoryEntry:
    """
    Represents a single memory stored by EON.
    """

    content: str

    memory_type: MemoryType

    importance: MemoryImportance = MemoryImportance.NORMAL

    embedding: list[float] | None = None

    id: UUID = field(default_factory=uuid4)

    created_at: datetime = field(default_factory=datetime.utcnow)

    metadata: dict[str, Any] = field(default_factory=dict)


# How similar a stored memory must be to count as relevant to the
# current topic. Cosine similarity against this embedding model gives
# *unrelated* text scores around 0.3–0.5, so a low bar returns memories
# that have nothing to do with the question — and recalled memories are
# injected into the prompt, so that noise changes EON's answers rather
# than just cluttering the log.
DEFAULT_MIN_SCORE = 0.55


@dataclass(slots=True)
class MemoryQuery:
    """
    Represents a search query against memory.
    """

    query: str

    limit: int = 10

    min_score: float = DEFAULT_MIN_SCORE


@dataclass(slots=True)
class MemorySearchResult:
    """
    Represents a retrieved memory and its relevance score.
    """

    memory: MemoryEntry

    score: float
