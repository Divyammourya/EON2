"""
Execution Executor.
"""

from __future__ import annotations

from src.modules.actions.executor import ActionExecutor
from src.modules.execution.models import ExecutionResult
from src.modules.planner.models import Plan


class ExecutionExecutor:
    """
    Executes an execution plan.
    """

    def __init__(
        self,
        executor: ActionExecutor,
    ) -> None:

        self._executor = executor

    def execute(
        self,
        plan: Plan,
    ) -> ExecutionResult:
        """Executes a plan's steps in order, stopping at the first
        failure instead of blindly running every remaining step.

        This is what makes multi-step plans (e.g. "organize my
        downloads, then email me a summary") safe to chain: if an
        earlier step fails, later steps that likely depended on it
        never run, and the failure — including the failed step's own
        result — is reported back rather than being silently masked by
        a later step's success.
        """

        results = []

        success = True

        for step in plan.steps:

            step.start()

            result = self._executor.execute(
                step.action,
            )

            step_failed = result is None or not result.success

            if result is not None:
                results.append(result)

            if step_failed:

                step.fail()

                success = False

                break

            step.complete()

        return ExecutionResult(
            plan=plan,
            results=results,
            success=success,
        )
