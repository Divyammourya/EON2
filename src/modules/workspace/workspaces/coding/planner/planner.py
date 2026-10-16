from __future__ import annotations

from .models import ExecutionPlan
from .rules import DEFAULT_RULES, PlanningRule
from .step import PlanStep


class Planner:
    """
    Converts a parsed action into an executable plan.

    The planner performs no filesystem operations, AI calls,
    or code editing. It simply decides *what* should happen.
    """

    def __init__(
        self,
        rules: tuple[PlanningRule, ...] = DEFAULT_RULES,
    ) -> None:

        self._rules = {
            rule.action: rule
            for rule in rules
        }

    def create_plan(
        self,
        *,
        action: str,
        arguments: dict[str, str] | None = None,
    ) -> ExecutionPlan:
        """
        Build an execution plan for a parsed action.

        `arguments` is a named-value map (e.g. {"path": "a.py"} or
        {"file": ..., "symbol": ..., "instruction": ...}). Every step
        produced by the rule receives the same map — each handler
        picks out the keys it needs, the same way every step
        previously received the same single `argument` string.
        """

        rule = self._rules.get(action)

        if rule is None:
            return ExecutionPlan(
                goal=action,
                steps=[],
            )

        resolved_arguments = arguments or {}

        steps = [
            PlanStep(
                type=step,
                arguments=dict(resolved_arguments),
            )
            for step in rule.steps
        ]

        return ExecutionPlan(
            goal=action,
            steps=steps,
        )

    def supports(
        self,
        action: str,
    ) -> bool:
        """
        Whether a planning rule exists.
        """

        return action in self._rules

    def available_actions(
        self,
    ) -> list[str]:
        """
        Return every supported planning action.
        """

        return sorted(
            self._rules.keys(),
        )
