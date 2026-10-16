"""
Perception Manager.
"""

from __future__ import annotations

from src.modules.perception.models import PerceptionResult
from src.modules.perception.perception import PerceptionEngine


class PerceptionManager:
    """
    Facade for the Perception Engine.
    """

    def __init__(self) -> None:
        self._engine = PerceptionEngine()

    def perceive(self) -> PerceptionResult:
        """
        Collect information from all available sensors.
        """

        return self._engine.perceive()
