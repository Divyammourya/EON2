"""
Embedding Service.
"""

from __future__ import annotations

from src.modules.ai.manager import AIManager


class EmbeddingService:

    def __init__(self) -> None:
        self._ai = AIManager()

    def embed(
        self,
        text: str,
    ) -> list[float]:

        return self._ai.embed(text)
