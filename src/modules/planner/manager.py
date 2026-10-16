"""
Planner Manager.

Public interface for the EON Planner.
"""

from __future__ import annotations

from src.modules.actions.models import Action
from src.modules.planner.models import Plan
from src.modules.planner.planner import Planner


class PlannerManager:
    """
    High-level interface for creating execution plans.
    """

    def __init__(self) -> None:
        self._planner = Planner()

    def create_plan(
        self,
        goal: str,
        action: Action,
    ) -> Plan:
        """
        Create a plan from a user goal.
        """

        return self._planner.create_plan(
            goal,
            action,
        )
