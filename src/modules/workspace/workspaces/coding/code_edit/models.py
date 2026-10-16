from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class EditRequest:
    """
    Represents a code edit requested by the AI.
    """

    file: Path
    symbol: str | None
    instruction: str


@dataclass(slots=True)
class EditResult:
    """
    Result of a code edit.
    """

    success: bool
    original: str
    updated: str
    message: str = ""
