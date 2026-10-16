"""
Reasoning Manager.

Public interface for the Reasoning module.
"""

from __future__ import annotations

from src.modules.planner.models import Plan
from src.modules.reasoning.models import ReasoningResult
from src.modules.reasoning.reasoner import Reasoner


class ReasoningManager:
    """
    High-level interface for reasoning.
    """

    def __init__(self) -> None:
        self._reasoner = Reasoner()

    def reason(
        self,
        plan: Plan,
    ) -> ReasoningResult:
        """
        Evaluate a plan before execution.
        """

        return self._reasoner.reason(plan)
