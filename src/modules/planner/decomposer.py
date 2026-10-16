"""
Goal Decomposer.

Responsible for breaking a goal into executable steps.
"""

from __future__ import annotations

from src.modules.actions.models import Action, ActionType
from src.modules.planner.models import Goal, Step


class GoalDecomposer:
    """
    Breaks a goal into executable steps.
    """

    def decompose(
        self,
        goal: Goal,
        action: Action,
    ) -> list[Step]:
        """
        Convert a goal into executable steps.

        Currently supports simple "and" decomposition.
        """

        text = goal.description.lower()

        # Commands are atomic — never split on " and ", since that
        # text may be part of the command itself (e.g. "echo hello
        # and goodbye").
        if action.type == ActionType.RUN_COMMAND:
            return [
                Step(action=action),
            ]

        # Single-step request
        if " and " not in text:
            return [
                Step(action=action),
            ]

        # Multi-step request
        parts = [
            part.strip()
            for part in goal.description.split(" and ")
        ]

        steps: list[Step] = []

        for part in parts:
            steps.append(
                Step(
                    action=Action(
                        type=action.type,
                        target=part.lower().replace("open ", "").strip(),
                    )
                )
            )

        return steps
