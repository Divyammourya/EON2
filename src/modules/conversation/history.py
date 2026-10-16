"""
Conversation history.
"""

from __future__ import annotations

from src.modules.conversation.message import Message


class ConversationHistory:
    """Stores conversation messages."""

    def __init__(self) -> None:
        self._messages: list[Message] = []

    def add(self, message: Message) -> None:
        self._messages.append(message)

    def clear(self) -> None:
        self._messages.clear()

    def messages(self) -> list[Message]:
        return self._messages.copy()

    def to_ollama(self) -> list[dict]:
        return [message.to_dict() for message in self._messages]
