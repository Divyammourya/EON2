"""
Execution Manager.
"""

from __future__ import annotations

from src.modules.execution.executor import ExecutionExecutor
from src.modules.execution.models import ExecutionResult
from src.modules.planner.models import Plan


class ExecutionManager:
    """
    Public interface for executing plans.
    """

    def __init__(
        self,
        executor: ExecutionExecutor,
    ) -> None:

        self._executor = executor

    def execute(
        self,
        plan: Plan,
    ) -> ExecutionResult:

        return self._executor.execute(
            plan,
        )
