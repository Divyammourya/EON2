"""
Planner.

Creates execution plans from user goals.
"""

from __future__ import annotations

from src.modules.actions.models import Action
from src.modules.planner.models import Goal, Plan
from src.modules.planner.decomposer import GoalDecomposer


class Planner:
    """Creates executable plans."""

    def __init__(self) -> None:
        self._decomposer = GoalDecomposer()

    def create_plan(
        self,
        goal: str,
        action: Action,
    ) -> Plan:
        """
        Generate an execution plan.
        """

        goal_object = Goal(
            description=goal,
        )

        steps = self._decomposer.decompose(
            goal_object,
            action,
        )

        return Plan(
            goal=goal_object,
            steps=steps,
        )
