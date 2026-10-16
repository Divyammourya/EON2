"""
Perception Engine.
"""

from __future__ import annotations

from src.modules.perception.models import (
    PerceptionItem,
    PerceptionResult,
)


class PerceptionEngine:
    """
    Collects information from available sensors.

    For now this is a placeholder.
    Later it will integrate:

    - Camera
    - Microphone
    - Screen
    - Clipboard
    - Files
    """

    def perceive(self) -> PerceptionResult:
        """
        Collect perception from all sensors.
        """

        items: list[PerceptionItem] = []

        return PerceptionResult(
            items=items,
        )
