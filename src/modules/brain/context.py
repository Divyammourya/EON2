"""
Context Builder.
"""

from __future__ import annotations

from datetime import datetime

# from src.modules.ai.prompts import SYSTEM_PROMPT
from src.modules.conversation.history import ConversationHistory

from src.modules.identity.manager import IdentityManager
from src.modules.tools.knowledge.web_search import WebPassage, format_grounding


def current_datetime_note(now: datetime) -> str:
    """Builds the system-prompt section that tells EON today's date.

    A language model has no clock. Asked for the date it will answer
    confidently from its training data — which is why EON used to
    insist it was February 2023 — so the real date and time are stated
    in the prompt on every turn. ``ContextBuilder.build`` calls this
    with the current time each time it runs, so it can never go stale.

    Args:
        now: The moment to describe. Passed in (rather than read here)
            so the output is deterministic and testable.

    Returns:
        The "Current date and time" section, ready to append to a
        system prompt.
    """
    return (
        "\n\nCurrent date and time\n"
        "---------------------\n"
        f"Today is {now.strftime('%A, %d %B %Y')}.\n"
        f"The current time is {now.strftime('%H:%M')} (local time).\n"
        "Whenever the user asks about the date, the day of the week, the "
        "month, the year, or the time, answer from the lines above. "
        "Never answer those from memory or training data.\n"
    )


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
        knowledge: list[WebPassage] | None = None,
    ) -> list[dict]:

        system_prompt = self.identity.system_prompt()
        system_prompt += current_datetime_note(datetime.now())

        if knowledge:
            system_prompt += format_grounding(knowledge)

        if history.summary:
            system_prompt += (
                "\n\nEarlier in this conversation\n"
                "-----------------------------\n"
                f"{history.summary}\n"
            )

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
