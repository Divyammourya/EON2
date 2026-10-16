"""
Reflection models.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.modules.execution.models import ExecutionResult


@dataclass(slots=True)
class ReflectionResult:
    """
    Result of reflecting on an execution.
    """

    execution: ExecutionResult

    learned: bool

    summary: str
