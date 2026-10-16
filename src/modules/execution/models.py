"""
Execution models.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.modules.actions.models import ActionResult
from src.modules.planner.models import Plan


@dataclass(slots=True)
class ExecutionResult:
    """
    Result of executing a plan.
    """

    plan: Plan

    results: list[ActionResult]

    success: bool
