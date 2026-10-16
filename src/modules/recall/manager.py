"""
Recall Manager.
"""

from __future__ import annotations

from src.modules.context.models import Context

from src.modules.recall.models import RecallResult
from src.modules.recall.recall import RecallEngine

from src.modules.memory.service import MemoryService


class RecallManager:
    """
    Coordinates memory retrieval.
    """

    def __init__(
        self,
        memory: MemoryService,
    ) -> None:

        self._memory = memory

        self._engine = RecallEngine(
            memory=memory,
        )

    def recall(
        self,
        context: Context,
    ) -> RecallResult:

        return self._engine.recall(
            context=context,
        )
