"""
Recall Engine.
"""

from __future__ import annotations

from src.modules.context.models import Context

from src.modules.recall.models import RecallResult

from src.modules.memory.service import MemoryService
from src.modules.memory.models import DEFAULT_MIN_SCORE, MemoryQuery


class RecallEngine:
    """
    Responsible for retrieving relevant memories.
    """

    def __init__(
        self,
        memory: MemoryService,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> None:
        """Configures the engine.

        Args:
            memory: Where memories are stored and searched.
            min_score: How similar a memory must be to the current topic
                to be recalled. Unrelated text scores 0.3–0.5 against
                this embedding model, so this is the difference between
                "relevant memories" and "whatever was nearest".
        """

        self._memory = memory
        self._min_score = min_score

    def recall(
        self,
        context: Context,
    ) -> RecallResult:

        query = MemoryQuery(
            query=context.topic,
            min_score=self._min_score,
        )

        results = self._memory.search(query)

        return RecallResult(
            memories=results,
        )
