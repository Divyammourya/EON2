"""
Context Manager.
"""

from __future__ import annotations

from src.modules.context.context import ContextEngine
from src.modules.context.models import Context
from src.modules.conversation.history import ConversationHistory


class ContextManager:
    """
    Public interface for building conversation context.
    """

    def __init__(self) -> None:

        self._engine = ContextEngine()

    def build(
        self,
        history: ConversationHistory,
        user_message: str,
    ) -> Context:

        return self._engine.build(
            history=history,
            user_message=user_message,
        )
