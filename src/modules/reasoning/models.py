"""
Reasoning models.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.modules.planner.models import Plan


@dataclass(slots=True)
class ReasoningResult:
    """
    Result produced by the Reasoner.
    """

    plan: Plan

    approved: bool

    message: str
