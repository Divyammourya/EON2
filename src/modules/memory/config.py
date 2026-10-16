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
