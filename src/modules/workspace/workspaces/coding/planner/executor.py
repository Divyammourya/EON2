from __future__ import annotations

from collections.abc import Callable

from .models import ExecutionContext, ExecutionPlan, PlanResult
from .step import PlanStep, StepType

Handler = Callable[[PlanStep, ExecutionContext], object]


class PlanExecutor:
    """
    Executes an ExecutionPlan.

    The executor owns no business logic itself.
    Instead it dispatches every step to a registered handler.
    """

    def __init__(self) -> None:

        self._handlers: dict[
            StepType,
            Handler,
        ] = {}

    def register(
        self,
        step: StepType,
        handler: Handler,
    ) -> None:
        """
        Register the function responsible for executing one step.
        """

        self._handlers[step] = handler

    def execute(
        self,
        plan: ExecutionPlan,
    ) -> PlanResult:
        """
        Execute every step in order.
        """

        context = ExecutionContext()

        completed = 0

        for step in plan.steps:

            handler = self._handlers.get(
                step.type,
            )

            if handler is None:

                return PlanResult(
                    success=False,
                    completed_steps=completed,
                    message=(
                        f"No handler registered for "
                        f"{step.type.value}"
                    ),
                    context=context,
                )

            result = handler(
                step,
                context,
            )

            # Every step's own return value is recorded under its
            # step type, in addition to whatever the handler itself
            # chose to `context.set(...)`. Without this, a plan's
            # individual step results (e.g. what `search` found, what
            # `read_file` returned) would be silently discarded and
            # only overall success/failure would ever reach the
            # caller.
            context.set(
                step.type.value,
                result,
            )

            completed += 1

        return PlanResult(
            success=True,
            completed_steps=completed,
            message="Plan executed successfully.",
            context=context,
        )
