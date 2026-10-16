"""
Reflection Reflector.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.logger import get_logger
from src.modules.execution.models import ExecutionResult
from src.modules.reflection.models import ReflectionResult

if TYPE_CHECKING:
    from src.modules.memory.service import MemoryService

logger = get_logger("Reflector")


class Reflector:
    """
    Reflects on completed executions.

    Also doubles as the correction-learning hook for the Hinglish
    phrase dictionary (Memory's ``learned_phrases`` table): when an
    execution fails and the very next execution succeeds, that's
    treated as "the user rephrased/corrected EON", and the *original*
    failed phrase is remembered as mapping to whatever action the
    corrected phrasing actually triggered — e.g. "notepad kolo"
    (misheard/misspelled) fails, the user says "notepad kholo" which
    succeeds, and "notepad kolo" is now mapped directly to
    OPEN_APP/"notepad" for next time.

    This is a simple, best-effort heuristic scoped to one Reflector
    instance's lifetime (in-memory ``_last_failed_goal``), not a
    guarantee that every failure immediately followed by a success is
    actually a correction of that specific failure — two genuinely
    unrelated requests back to back would also match this pattern.
    """

    def __init__(self, memory: "MemoryService | None" = None) -> None:
        # Optional: without Memory, reflection still works exactly as
        # before, just without correction-learning.
        self._memory = memory
        self._last_failed_goal: str | None = None

    def reflect(
        self,
        execution: ExecutionResult,
    ) -> ReflectionResult:

        goal_text = execution.plan.goal.description.strip()

        if execution.success:
            self._maybe_learn_correction(goal_text, execution)
            self._last_failed_goal = None

            return ReflectionResult(
                execution=execution,
                learned=True,
                summary="Execution succeeded.",
            )

        self._last_failed_goal = goal_text

        return ReflectionResult(
            execution=execution,
            learned=False,
            summary="Execution failed.",
        )

    def _maybe_learn_correction(
        self,
        goal_text: str,
        execution: ExecutionResult,
    ) -> None:
        """
        If the previous execution failed and this one succeeded with
        different phrasing, persist the *previous* (failed) phrase as
        a learned mapping to this execution's action.
        """
        if self._memory is None:
            return

        if not self._last_failed_goal or self._last_failed_goal == goal_text:
            return

        if not execution.plan.steps:
            return

        # Corrections in this codebase are single-action turns in
        # practice; use the first step as the representative action
        # for the learned mapping.
        action = execution.plan.steps[0].action

        try:
            self._memory.set_learned_phrase(
                self._last_failed_goal,
                action.type.value,
                action.target,
            )
        except Exception:
            # Learning a correction is a best-effort convenience, not
            # something that should ever break the actual reflection
            # flow if the store has an issue.
            logger.warning(
                "Failed to persist learned phrase for %r.",
                self._last_failed_goal,
                exc_info=True,
            )
