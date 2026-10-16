"""
Decision Engine.
"""

from __future__ import annotations

from src.modules.brain.models import BrainDecision
from src.modules.brain.models import DecisionType


class DecisionEngine:
    """
    Decides what EON should do.
    """

    def decide(
        self,
        user_message: str,
    ) -> BrainDecision:

        message = user_message.lower()

        if any(
            word in message
            for word in (
                "open",
                "launch",
                "start",
                "run",
            )
        ):
            return BrainDecision(
                decision=DecisionType.TOOL,
            )

        if any(
            word in message
            for word in (
                "remember",
                "memory",
            )
        ):
            return BrainDecision(
                decision=DecisionType.MEMORY,
            )

        return BrainDecision(
            decision=DecisionType.CHAT,
        )
