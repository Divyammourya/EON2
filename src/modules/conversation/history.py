"""
Conversation history.
"""

from __future__ import annotations

from src.modules.conversation.message import Message


class ConversationHistory:
    """Stores conversation messages."""

    def __init__(self) -> None:
        self._messages: list[Message] = []
        self._summary = ""

    def add(self, message: Message) -> None:
        self._messages.append(message)

    def clear(self) -> None:
        self._messages.clear()
        self._summary = ""

    @property
    def summary(self) -> str:
        """The running summary of the compacted earlier conversation.

        Empty until ``apply_compaction`` has been called at least once
        (see conversation/compaction.py).
        """
        return self._summary

    def apply_compaction(self, summary: str, recent: list[Message]) -> None:
        """Replaces the folded-away messages with ``summary``.

        Called by ``Brain`` once it has summarised the older part of the
        conversation. The recent turns passed in are kept verbatim; the
        summary stands in for everything before them.
        """
        self._summary = summary
        self._messages = list(recent)

    def messages(self) -> list[Message]:
        return self._messages.copy()

    def to_ollama(self) -> list[dict]:
        return [message.to_dict() for message in self._messages]
