"""
Brain Manager.
"""

from __future__ import annotations

from src.modules.ai.manager import AIManager
from src.modules.brain.context import ContextBuilder
from src.modules.brain.decision import DecisionEngine
from src.modules.conversation.history import ConversationHistory

from src.modules.identity.manager import IdentityManager
from src.modules.tools.knowledge.web_search import WebPassage, WebSearchClient


class Brain:

    def __init__(
        self,
        identity: IdentityManager,
        knowledge: WebSearchClient | None = None,
    ) -> None:

        self.ai = AIManager()
        self.context = ContextBuilder(
            identity=identity,
        )
        self.decision = DecisionEngine()

        self.identity = identity
        self.knowledge = knowledge if knowledge is not None else WebSearchClient()

    def _knowledge_for(self, user_message: str) -> list[WebPassage]:
        """Looks the question up on the web, when it's the kind that needs it.

        Returns passages to ground this turn with, or an empty list when
        the question doesn't need the web or the lookup failed — either
        way the reply proceeds exactly as it did before.
        """
        passages = self.knowledge.grounding_for(user_message)

        if passages:
            print(f"[Web] {len(passages)} result(s) for {user_message!r}")

        return passages

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
            knowledge=self._knowledge_for(user_message),
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
            knowledge=self._knowledge_for(user_message),
        )

        yield from self.ai.chat_stream(context)
