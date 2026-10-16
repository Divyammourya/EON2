"""
Perception models.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PerceptionItem:
    """
    A single perceived piece of information.
    """

    source: str
    content: str
    confidence: float = 1.0


@dataclass(slots=True)
class PerceptionResult:
    """
    Result returned by the Perception module.
    """

    items: list[PerceptionItem] = field(default_factory=list)

    @property
    def has_items(self) -> bool:
        return len(self.items) > 0
