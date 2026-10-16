"""
Brain Manager.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.modules.ai.manager import AIManager
from src.modules.brain.context import ContextBuilder
from src.modules.brain.decision import DecisionEngine
from src.modules.conversation.compaction import (
    build_compaction_messages,
    needs_compaction,
    split_for_compaction,
)
from src.modules.conversation.history import ConversationHistory

from src.modules.identity.manager import IdentityManager
from src.modules.tools.knowledge.web_search import WebPassage, WebSearchClient
from src.modules.tools.utility.skills import LocalSkills

logger = get_logger("Brain")


class Brain:

    def __init__(
        self,
        identity: IdentityManager,
        knowledge: WebSearchClient | None = None,
        skills: LocalSkills | None = None,
        max_history_messages: int = 40,
        keep_recent_messages: int = 12,
    ) -> None:

        self.ai = AIManager()
        self.context = ContextBuilder(
            identity=identity,
        )
        self.decision = DecisionEngine()

        self.identity = identity
        self.knowledge = knowledge if knowledge is not None else WebSearchClient()
        self.skills = skills if skills is not None else LocalSkills()

        self._max_history_messages = max_history_messages
        self._keep_recent_messages = keep_recent_messages

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

    def _compact_history(self, history: ConversationHistory) -> None:
        """Folds the older part of a long conversation into a summary.

        Runs before the prompt is built. Without this a session that
        outgrows the context window silently loses its oldest turns and
        EON forgets what it was doing; with it, those turns survive as a
        few lines of notes. Never raises — a failed summary just leaves
        the history as it is and the turn continues.
        """
        if not needs_compaction(
            len(history.messages()),
            self._max_history_messages,
        ):
            return

        older, recent = split_for_compaction(
            history.messages(),
            self._keep_recent_messages,
        )

        if not older:
            return

        try:
            summary = self.ai.chat(
                build_compaction_messages(older, history.summary)
            ).strip()
        except Exception:
            logger.exception(
                "Failed to summarise the conversation; keeping it as is."
            )
            return

        if not summary:
            return

        history.apply_compaction(summary, recent)

        print(
            f"[Memory] Folded {len(older)} older message(s) into the summary."
        )

    def think(
        self,
        history: ConversationHistory,
        user_message: str,
        memories: list[str],
    ) -> str:

        direct = self.skills.answer(user_message)

        if direct is not None:
            print("[Skills] Answered locally (no model call).")
            return direct

        decision = self.decision.decide(
            user_message,
        )

        print(
            f"[Brain] Decision: {decision.decision.value}"
        )

        self._compact_history(history)

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

        direct = self.skills.answer(user_message)

        if direct is not None:
            print("[Skills] Answered locally (no model call).")
            yield direct
            return

        decision = self.decision.decide(
            user_message,
        )

        print(
            f"[Brain] Decision: {decision.decision.value}"
        )

        self._compact_history(history)

        context = self.context.build(
            history=history,
            memories=memories,
            knowledge=self._knowledge_for(user_message),
        )

        yield from self.ai.chat_stream(context)
