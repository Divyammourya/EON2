"""
Store Engine.
"""

from __future__ import annotations

from src.modules.store.models import StoreDecision


class StoreEngine:
    """
    Decides whether something should be stored in long-term memory.
    """

    def decide(
        self,
        user_message: str,
        assistant_message: str,
    ) -> StoreDecision:

        text = user_message.lower()

        keywords = (
            "my name",
            "i like",
            "i love",
            "i prefer",
            "remember",
            "favorite",
            "always",
            "never",
        )

        if any(keyword in text for keyword in keywords):

            return StoreDecision(
                should_store=True,
                content=user_message,
                reason="Potential long-term user preference.",
            )

        return StoreDecision(
            should_store=False,
            content="",
            reason="No long-term information detected.",
        )
