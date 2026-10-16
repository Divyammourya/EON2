"""
Context Builder.
"""

from __future__ import annotations

# from src.modules.ai.prompts import SYSTEM_PROMPT
from src.modules.conversation.history import ConversationHistory

from src.modules.identity.manager import IdentityManager


class ContextBuilder:
    """
    Builds the context sent to the LLM.
    """

    def __init__(
        self,
        identity: IdentityManager,
    ) -> None:

        self.identity = identity

    def build(
        self,
        history: ConversationHistory,
        memories: list[str],
    ) -> list[dict]:

        system_prompt = self.identity.system_prompt()

        if memories:

            system_prompt += "\n\nRelevant long-term memories:\n"

            for memory in memories:
                system_prompt += f"- {memory}\n"

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

        messages.extend(
            history.to_ollama()
        )

        return messages
