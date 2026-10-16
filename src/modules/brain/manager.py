"""
Brain Manager.
"""

from __future__ import annotations

from src.modules.ai.manager import AIManager
from src.modules.brain.context import ContextBuilder
from src.modules.brain.decision import DecisionEngine
from src.modules.conversation.history import ConversationHistory

from src.modules.identity.manager import IdentityManager



class Brain:

    def __init__(
        self,
        identity: IdentityManager,
    ) -> None:

        self.ai = AIManager()
        self.context = ContextBuilder(
            identity=identity,
        )
        self.decision = DecisionEngine()

        self.identity = identity


    def think(
        self,
        history: ConversationHistory,
        user_message: str,
        memories: list[str],
    ) -> str:

        decision = self.decision.decide(
            user_message,
        )

        print(
            f"[Brain] Decision: {decision.decision.value}"
        )

        context = self.context.build(
            history=history,
            memories=memories,
        )

        return self.ai.chat(context)

    def think_stream(
        self,
        history: ConversationHistory,
        user_message: str,
        memories: list[str],
    ):
        """
        Same as ``think``, but yields the reply as incremental text
        deltas instead of waiting for the full reply.
        """

        decision = self.decision.decide(
            user_message,
        )

        print(
            f"[Brain] Decision: {decision.decision.value}"
        )

        context = self.context.build(
            history=history,
            memories=memories,
        )

        yield from self.ai.chat_stream(context)
