from __future__ import annotations

from collections.abc import Callable

from .models import ExecutionContext, ExecutionPlan, PlanResult
from .step import PlanStep, StepType

Handler = Callable[[PlanStep, ExecutionContext], object]


def _step_failure(result: object) -> str | None:
    """The reason a step failed, or ``None`` if it succeeded.

    Handlers report failure by *returning* a dict rather than by
    raising — e.g. ``CodingAgent.create_file`` returns
    ``{"success": False, "error": "..."}``. Without checking that, a
    plan reports "executed successfully" for a step that did nothing,
    which for a coding agent means EON telling you it wrote your code
    when it hadn't. That is worse than an error, because you only find
    out by looking.

    A result with no ``success`` field at all (some handlers return
    plain objects, e.g. the repository indexer) counts as success —
    absence of a failure signal is not a failure.
    """
    if isinstance(result, dict):
        if result.get("success") is False:
            return str(
                result.get("error")
                or result.get("message")
                or "unknown error"
            )
        return None

    if getattr(result, "success", None) is False:
        return str(
            getattr(result, "error", None)
            or getattr(result, "message", None)
            or "unknown error"
        )

    return None


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
            # chose to ``context.set(...)``. Without this, a plan'
            # individual step results (e.g. what `search` found, what
            # `read_file` returned) would be silently discarded and
            # only overall success/failure would ever reach the
            # caller.
            context.set(
                step.type.value,
                result,
            )

            failure = _step_failure(result)

            if failure is not None:
                # Stop at the first failure: a later step usually
                # depends on an earlier one having worked, so
                # carrying on would produce a cascade of confusing
                # secondary errors on top of the real one.
                return PlanResult(
                    success=False,
                    completed_steps=completed,
                    message=(
                        f"{step.type.value} failed: {failure}"
                    ),
                    context=context,
                )

            completed += 1

        return PlanResult(
            success=True,
            completed_steps=completed,
            message="Plan executed successfully.",
            context=context,
        )
