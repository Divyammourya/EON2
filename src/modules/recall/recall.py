"""
Recall Engine.
"""

from __future__ import annotations

from src.modules.context.models import Context

from src.modules.recall.models import RecallResult

from src.modules.memory.service import MemoryService
from src.modules.memory.models import MemoryQuery


class RecallEngine:
    """
    Responsible for retrieving relevant memories.
    """

    def __init__(
        self,
        memory: MemoryService,
    ) -> None:

        self._memory = memory

    def recall(
        self,
        context: Context,
    ) -> RecallResult:

        query = MemoryQuery(
            query=context.topic,
        )

        results = self._memory.search(query)

        return RecallResult(
            memories=results,
        )
