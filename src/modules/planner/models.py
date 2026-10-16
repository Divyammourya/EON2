"""
Planner models.

Defines the core planning objects used by EON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.modules.actions.models import Action


class StepStatus(Enum):
    """Execution status of a plan step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Goal:
    """User objective."""

    description: str


@dataclass
class Step:
    """One executable step."""

    action: Action
    status: StepStatus = StepStatus.PENDING

    def start(self) -> None:
        """Mark the step as running."""
        self.status = StepStatus.RUNNING

    def complete(self) -> None:
        """Mark the step as completed."""
        self.status = StepStatus.COMPLETED

    def fail(self) -> None:
        """Mark the step as failed."""
        self.status = StepStatus.FAILED


@dataclass
class Plan:
    """Collection of executable steps."""

    goal: Goal
    steps: list[Step] = field(default_factory=list)

    def add_step(self, action: Action) -> None:
        self.steps.append(
            Step(action=action)
        )
