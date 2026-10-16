"""
Monitor models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.modules.execution.models import ExecutionResult


@dataclass(slots=True)
class MonitorResult:
    """
    Result of monitoring an executed plan.
    """

    execution: ExecutionResult

    success: bool

    message: str


@dataclass(slots=True)
class AmbientSignal:
    """
    Something EON noticed without being asked.
    """

    id: str
    kind: str
    title: str
    message: str
    severity: str = "info"
    observed_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
