"""
Context Engine.
"""

from __future__ import annotations

from src.modules.context.models import Context
from src.modules.conversation.history import ConversationHistory


class ContextEngine:
    """
    Builds the current conversational context.
    """

    def build(
        self,
        history: ConversationHistory,
        user_message: str,
    ) -> Context:

        context = Context()

        messages = history.messages()

        if messages:

            for message in reversed(messages):

                if message.role == "assistant":

                    context.last_assistant_message = message.content

                    break

        context.topic = user_message

        return context
