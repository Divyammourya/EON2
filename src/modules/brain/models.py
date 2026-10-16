"""
Brain data models.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DecisionType(str, Enum):
    """Possible decisions made by the Brain."""

    CHAT = "chat"
    TOOL = "tool"
    MEMORY = "memory"
    SYSTEM = "system"


@dataclass(slots=True)
class BrainDecision:
    """Represents the Brain's decision."""

    decision: DecisionType
    confidence: float = 1.0
