"""
Memory Configuration.

Configuration models for the Memory subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class MemoryConfig:
    """
    Configuration for the Memory subsystem.
    """

    database_path: Path = Path("data/memory.db")

    autosave: bool = True

    max_working_memory: int = 100

    max_search_results: int = 10

    duplicate_threshold: float = 0.95

    #: How quickly being old stops counting against a memory. At the
    #: default, a memory from a year ago still ranks at about 92% of a
    #: brand-new one — the intent is to break ties between equally
    #: relevant memories, never to bury something durable.
    recency_half_life_days: float = 90.0

    #: What ``prune`` will remove if asked to: memories below this
    #: importance, older than this many days. Nothing prunes on its
    #: own — see ``SQLiteMemoryStore.prune``.
    prune_after_days: int = 180

    prune_below_importance: int = 2  # MemoryImportance.NORMAL
