from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PatchOperation:
    """
    Represents one file modification.
    """

    file: Path
    original: str
    updated: str


@dataclass(slots=True)
class PatchResult:
    """
    Result of applying a patch.
    """

    success: bool

    changed_files: int

    operations: list[PatchOperation]

    message: str = ""
