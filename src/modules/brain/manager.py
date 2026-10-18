"""
Brain Manager.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.modules.ai.manager import AIManager
from src.modules.brain.context import ContextBuilder
from src.modules.brain.decision import DecisionEngine
from src.modules.brain.verification import Verdict, Verifier, hedged
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
        self.verifier = Verifier()

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

        knowledge = self._knowledge_for(user_message)

        context = self.context.build(
            history=history,
            memories=memories,
            knowledge=knowledge,
        )

        return self._verified(self.ai.chat(context), knowledge)

    def _verified(
        self,
        answer: str,
        knowledge: list[WebPassage],
    ) -> str:
        """Checks an answer against its evidence, and hedges if needed.

        Only runs on turns that actually used the web, since there is
        nothing to check an ungrounded answer against. Never raises: a
        check that fails leaves the answer exactly as the model wrote
        it, which is what EON did before this existed.

        Args:
            answer: What the model wrote.
            knowledge: The passages it was grounded in.

        Returns:
            The answer, prefixed when a claim in it was not backed.
        """
        if not knowledge:
            return answer

        verdict = self.verifier.check(answer, knowledge)

        print(f"[Verify] {verdict.value}")

        if verdict is Verdict.UNSUPPORTED:
            logger.info(
                "Answer went beyond the sources found; hedging it."
            )

        return hedged(answer, verdict)

    def think_stream(
        self,
        history: ConversationHistory,
        user_message: str,
        memories: list[str],
    ):
        """
        Same pipeline and side effects as ``think``, but yields the
        reply as text deltas.

        The answer is buffered before it is yielded, rather than passed
        through as it arrives, because the verification check needs the
        whole thing and the hedge has to be in place before the user
        hears any of it. That gives up the first-token latency
        streaming was there for — affordable now that the model stays
        resident and a turn takes a second or two, and worth it to
        avoid saying something and then correcting it.
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

        knowledge = self._knowledge_for(user_message)

        context = self.context.build(
            history=history,
            memories=memories,
            knowledge=knowledge,
        )

        answer = "".join(self.ai.chat_stream(context))

        yield self._verified(answer, knowledge)
