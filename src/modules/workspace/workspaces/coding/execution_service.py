from __future__ import annotations

from .planner import ExecutionPlan, PlanExecutor


class ExecutionService:
    """
    Bridges the planner and executor.

    Given an ExecutionPlan, this class is responsible
    for executing it and returning the final result.

    Later it will also provide:

    • progress reporting
    • cancellation
    • retries
    • logging
    • streaming updates
    """

    def __init__(
        self,
        executor: PlanExecutor,
    ) -> None:
        self._executor = executor

    def execute(
        self,
        plan: ExecutionPlan,
    ):
        return self._executor.execute(plan)
