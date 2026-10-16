"""
Store Manager.
"""

from __future__ import annotations

from src.modules.store.models import StoreDecision
from src.modules.store.store import StoreEngine

from src.modules.memory.service import MemoryService

from src.modules.memory.models import (
    MemoryEntry,
    MemoryImportance,
    MemoryType,
)

from src.modules.store.extractor import MemoryExtractor

from src.modules.ai.manager import AIManager

class StoreManager:
    """
    Facade for the Store Engine.
    """

    def __init__(
        self,
        memory: MemoryService,
    ) -> None:

        self._memory = memory
        self._engine = StoreEngine()
        self._extractor = MemoryExtractor()
        self._ai = AIManager()



    def decide(
        self,
        user_message: str,
        assistant_message: str,
    ) -> StoreDecision:

        decision = self._engine.decide(
            user_message=user_message,
            assistant_message=assistant_message,
        )

        if decision.should_store:

            content = self._extractor.extract(
                decision.content,
            )

            embedding = self._ai.embed(content)

            memory = MemoryEntry(
                content=content,
                embedding=embedding,
                memory_type=MemoryType.CONVERSATION,
                importance=MemoryImportance.NORMAL,
            )

            # self._memory.save(memory)
            # if not self._memory.exists(content):
            #     self._memory.save(memory)
            exists = self._memory.exists(content)

            print(f"[Duplicate Check] {exists}")

            if not exists:
                print("[Store] Saving memory")
                self._memory.save(memory)
            else:
                print("[Store] Duplicate memory skipped")

        return decision
