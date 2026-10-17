"""
Conversation Manager.
"""

from __future__ import annotations

from src.modules.brain.manager import Brain
from src.modules.conversation.history import ConversationHistory
from src.modules.conversation.message import Message

from src.modules.intent import IntentManager
from src.modules.intent.models import IntentType
from src.modules.intent.tool_router import ToolRouter
from src.modules.actions import ActionRouter
from src.modules.actions.models import Action, ActionType

from src.modules.planner import PlannerManager
from src.modules.planner.models import Goal, Plan, Step
from src.modules.planner.multi_step import MultiStepSplitter

from src.modules.execution.manager import ExecutionManager

from src.modules.monitor import MonitorManager

from src.modules.reasoning import ReasoningManager

from src.modules.reflection import ReflectionManager

from src.modules.context import ContextManager

from src.modules.recall import RecallManager

from src.modules.store import StoreManager

from src.modules.perception import PerceptionManager

from src.modules.permissions.manager import PermissionManager
from src.modules.permissions.models import ConfirmationOutcome, PermissionLevel

from src.modules.memory.service import MemoryService

class ConversationManager:

    def __init__(
        self,
        history: ConversationHistory,
        brain: Brain,
        perception: PerceptionManager,
        context: ContextManager,
        recall: RecallManager,
        store: StoreManager,
        intent: IntentManager,
        planner: PlannerManager,
        reasoning: ReasoningManager,
        router: ActionRouter,
        execution: ExecutionManager,
        monitor: MonitorManager,
        reflection: ReflectionManager,
        permissions: PermissionManager,
        memory: MemoryService | None = None,
        tool_router: ToolRouter | None = None,
    ) -> None:

        self.history = history
        self.brain = brain
        self.perception = perception
        self.context = context
        self.recall = recall
        self.store = store
        self.intent = intent
        self.planner = planner
        self.reasoning = reasoning
        self.router = router
        self.execution = execution
        self.monitor = monitor
        self.reflection = reflection
        self.permissions = permissions
        self.memory = memory

        # Built on first use rather than here: it needs the AI provider,
        # and a session that never sees an unmatched message should not
        # pay for one. See ``tool_router``.
        self._tool_router = tool_router

        # Stateless — constructed here rather than injected, since it
        # has no dependencies of its own (see MultiStepSplitter).
        self.multi_step = MultiStepSplitter()

    def _summarize_results(self, results: list) -> str:
        """Builds the final response text for a plan's execution.

        A single-step plan returns that step's message unchanged —
        identical to the previous behavior, so ordinary one-action
        requests are unaffected. A multi-step plan combines every
        step's message into one consolidated report, since the user
        should hear what the whole chain did (including a step that
        failed partway through, which is included here too, since
        ``ExecutionExecutor`` now appends a failing step's own result
        before stopping) — not just whichever step happened to run
        last. This is still a single final message, not one message
        per step along the way.
        """
        if not results:
            return "Done."

        if len(results) == 1:
            return results[0].message

        parts = [
            f"{index}. {result.message}"
            for index, result in enumerate(results, start=1)
        ]

        return "Here's what I did:\n" + "\n".join(parts)

    def _handle_pending_confirmation(self, user_message: str) -> str | None:
        """
        Checks whether a previous risky action is still waiting on a
        yes/no, and if so, resolves it using ``user_message`` instead
        of treating it as a fresh command.

        Shared by ``ask`` and ``ask_stream``, called before either
        touches the normal pipeline — a pending confirmation takes
        priority over intent detection entirely, so a stray "delete
        it" can't slip past a "yes" that was actually meant for
        something else.

        Returns:
            The response text if a pending confirmation was resolved
            (confirmed, denied, or still waiting on a real answer), or
            ``None`` if there was nothing pending / it had expired —
            in which case the caller should proceed with its normal
            pipeline for ``user_message``.
        """
        if not self.permissions.has_pending():
            return None

        outcome, pending = self.permissions.resolve(user_message)

        if outcome == ConfirmationOutcome.CONFIRMED:

            execution = self.execution.execute(pending.plan)

            monitor = self.monitor.monitor(execution)

            print(f"[Executed Plan] {execution.plan}")
            print(f"[Monitor] {monitor}")

            reflection = self.reflection.reflect(execution)

            print(f"[Reflection] {reflection}")

            response = self._summarize_results(execution.results)

            self.history.add(Message(role="user", content=user_message))

            store_decision = self.store.decide(
                user_message=user_message,
                assistant_message=response,
            )

            print(f"[Store] {store_decision}")

            self.history.add(Message(role="assistant", content=response))

            return response

        if outcome == ConfirmationOutcome.DENIED:
            response = "Okay, cancelled."

            self.history.add(Message(role="user", content=user_message))
            self.history.add(Message(role="assistant", content=response))

            return response

        if outcome == ConfirmationOutcome.EXPIRED:
            # The window to confirm passed. Treat this message as a
            # brand-new request instead of responding about a
            # confirmation that's no longer valid.
            return None

        # NOT_A_RESPONSE: something's still pending, but this message
        # doesn't read as a yes/no — so the user has moved on to
        # something else. Drop the pending action and answer what they
        # actually asked.
        #
        # This used to re-prompt instead, reasoning that silently
        # dropping the action would defeat the point of asking. That
        # was wrong in practice, and the logs showed why: dropping is
        # the *safe* direction (the action doesn't run), while
        # re-prompting meant one unanswered question blocked every
        # later request. The user could not ask for the weather, or
        # for music, or for anything at all, until they worked out
        # that they had to say "no" to a question they had already
        # stopped caring about.
        #
        # So: a pending confirmation outranks a *yes or no*. It does
        # not outrank a new request.
        self.permissions.discard()

        return None

    def _run_pipeline(self, user_message: str):
        """
        Runs everything that has to happen before EON can decide *how*
        to respond: perception, context building, memory recall, intent
        detection, routing, planning, and reasoning. Also appends the
        user's message to history.

        Shared by ``ask`` and ``ask_stream`` so the two can't drift
        apart — they differ only in the final step (a canned/tool
        response vs. a Brain-generated reply, streamed or not).

        Returns:
            A ``(recall_result, action, plan, reasoning)`` tuple with
            everything the caller needs to decide what happens next.
        """

        perception = self.perception.perceive()

        print(f"[Perception] {perception}")

        context = self.context.build(
            history=self.history,
            user_message=user_message,
        )

        self.history.add(
            Message(
                role="user",
                content=user_message,
            )
        )

        print(f"[Context] {context}")

        recall_result = self.recall.recall(
            context=context,
        )

        print("[Recall]")
        for result in recall_result.memories:
            print(
                f"  Score={result.score:.3f} | "
                f"{result.memory.content}"
            )

        plan, action = self._build_plan_and_action(user_message)

        print(f"[Intent/Action] {action}")
        print(f"[Plan] {plan}")

        reasoning = self.reasoning.reason(plan)

        print(f"[Reasoning] {reasoning}")

        return recall_result, action, plan, reasoning

    @property
    def tool_router(self) -> ToolRouter:
        """The fallback that lets the model pick a tool. Built on use."""
        if self._tool_router is None:
            self._tool_router = ToolRouter()

        return self._tool_router

    def _detect_action(self, text: str) -> Action:
        """
        Resolves ``text`` to an Action, checking the learned-phrase
        dictionary (Memory's ``learned_phrases`` table) before falling
        back to normal intent classification and routing.

        This is the read side of the Hinglish personal-phrase-memory
        feature: if the user previously corrected EON after this exact
        (normalized) phrase failed, Reflection will have persisted a
        phrase -> Action mapping for it (see
        ``Reflector._maybe_learn_correction``). A hit here skips
        intent classification and routing entirely and reconstructs
        the Action directly from what was persisted — going through
        ``Intent`` instead would be a lossy round-trip through a
        different enum, since what's actually stored is an
        ``ActionType`` value and target, not an ``IntentType``.

        This is a plain phrase dictionary, not real speech-model
        personalization: it only ever recognizes the *exact*
        (normalized) phrase it was taught, never a paraphrase or a
        variation of it, and there's no fuzzy matching.

        Args:
            text: The message (or sub-goal, for a chained request) to
                resolve to an Action.

        Returns:
            The learned Action if ``text`` matches a stored phrase and
            it still maps to a valid ``ActionType``; otherwise, the
            usual ``intent.detect`` → ``router.route`` result.
        """
        if self.memory is not None:
            learned = self.memory.get_learned_phrase(text)

            if learned is not None:
                action_type_value, target = learned

                try:
                    return Action(type=ActionType(action_type_value), target=target)
                except ValueError:
                    # Stored value doesn't match any current ActionType
                    # (e.g. left over from a renamed/removed one) —
                    # fall through to normal detection instead of
                    # raising over a stale row.
                    pass

        intent = self.intent.detect(text)

        # When the keyword rules find nothing, the message is about to
        # go to the chat brain — which will happily *talk about* a
        # request it could have carried out. Give the model one chance
        # to name a tool instead.
        #
        # Only on the miss, so the fast path is untouched, and the
        # choice still goes through ``router.route`` and the permission
        # layer below: the model decides what the request *meant*, not
        # whether it may happen.
        if intent.type is IntentType.CHAT:
            chosen = self.tool_router.choose(text)

            if chosen is not None:
                intent = chosen

        return self.router.route(intent)

    def _build_plan_and_action(self, user_message: str) -> tuple[Plan, Action]:
        """Builds the plan for ``user_message`` and picks the
        "representative" action used for the CHAT-vs-action branch
        further down the pipeline.

        Most messages describe one task and use the existing
        single-action classify → route → ``PlannerManager`` path
        unchanged. If the message chains multiple tasks together (e.g.
        "organize my downloads, then email me a summary"), each
        sub-goal is classified and routed independently — since a
        later step may need a completely different action type than
        an earlier one — and combined into one Plan with multiple,
        independently-typed steps.

        The representative action matters because ``_run_non_chat_action``
        checks it to decide whether to fall through to Brain for a
        plain chat reply. For a chained plan, that must reflect
        whether *any* step is a real action — using only the first
        sub-goal's classification (or a classification of the whole,
        unsplit message) risks wrongly falling back to chat when a
        later step in the chain is the one that's actionable.

        Returns:
            A ``(plan, action)`` pair.
        """
        sub_goals = self.multi_step.split(user_message)

        if len(sub_goals) <= 1:
            action = self._detect_action(user_message)
            plan = self.planner.create_plan(
                goal=user_message,
                action=action,
            )
            return plan, action

        steps: list[Step] = []
        representative_action = None

        for sub_goal in sub_goals:
            sub_action = self._detect_action(sub_goal)
            steps.append(Step(action=sub_action))

            if representative_action is None or (
                representative_action.type == ActionType.CHAT
                and sub_action.type != ActionType.CHAT
            ):
                representative_action = sub_action

        plan = Plan(
            goal=Goal(description=user_message),
            steps=steps,
        )

        return plan, representative_action

    def _confirmation_prompt(self, pending) -> str:
        """
        Builds the message EON shows when first asking for
        confirmation — different wording for a plain CONFIRM (yes/no)
        vs. a high-risk VERIFY action (needs the authorization
        passphrase, not just a yes/no).
        """
        if pending.level == PermissionLevel.VERIFY and self.permissions.passphrase_configured:
            return (
                f"This is a high-risk action: {pending.description}. "
                "Say the authorization passphrase to proceed, or "
                "'cancel' to back out."
            )

        if pending.level == PermissionLevel.VERIFY:
            # No passphrase configured — still flag it as high-risk so
            # the user knows this tier exists, even though it's
            # currently only gated by a plain yes/no underneath.
            return (
                f"This is a high-risk action: {pending.description}. "
                "No authorization passphrase is configured, so a "
                "plain 'yes' will approve it — say 'yes' to proceed, "
                "or 'no' to cancel. (Set AUTHORIZATION_PASSPHRASE in "
                ".env to require more than a yes/no for actions like "
                "this.)"
            )

        return (
            f"This will {pending.description}. "
            "Say 'yes' to proceed, or 'no' to cancel."
        )

    def _run_non_chat_action(
        self,
        user_message: str,
        action,
        plan,
        reasoning,
    ) -> str | None:
        """
        Handles the non-CHAT branch (declined action, or a tool/action
        that was executed) and returns its final response text.

        Returns:
            The response text if this action produced one, or ``None``
            if the caller should fall through to the Brain for a CHAT
            reply instead. ``None`` covers both "this was a CHAT-type
            action to begin with" and the (pre-existing) edge case
            where a non-CHAT action was approved and executed but
            produced no results — both fell through to the Brain in the
            original, non-streaming ``ask`` and still do here.
        """

        if action.type.name == "CHAT":
            return None

        if not reasoning.approved:

            store_decision = self.store.decide(
                user_message=user_message,
                assistant_message=reasoning.message,
            )

            print(f"[Store] {store_decision}")

            self.history.add(
                Message(
                    role="assistant",
                    content=reasoning.message,
                )
            )

            return reasoning.message

        if self.permissions.classify(plan) != PermissionLevel.AUTO:

            pending = self.permissions.request(plan)
            response = self._confirmation_prompt(pending)

            self.history.add(
                Message(
                    role="assistant",
                    content=response,
                )
            )

            return response

        execution = self.execution.execute(plan)

        monitor = self.monitor.monitor(execution)

        print(f"[Executed Plan] {execution.plan}")
        print(f"[Monitor] {monitor}")

        reflection = self.reflection.reflect(execution)

        print(f"[Reflection] {reflection}")

        if execution.results:

            response = self._summarize_results(execution.results)

            store_decision = self.store.decide(
                user_message=user_message,
                assistant_message=response,
            )

            print(f"[Store] {store_decision}")

            self.history.add(
                Message(
                    role="assistant",
                    content=response,
                )
            )

            return response

        return None

    def ask(self, user_message: str) -> str:

        pending_response = self._handle_pending_confirmation(user_message)

        if pending_response is not None:
            return pending_response

        recall_result, action, plan, reasoning = self._run_pipeline(
            user_message,
        )

        non_chat_response = self._run_non_chat_action(
            user_message, action, plan, reasoning,
        )

        if non_chat_response is not None:
            return non_chat_response

        response = self.brain.think(
            history=self.history,
            user_message=user_message,
            memories=[
                result.memory.content
                for result in recall_result.memories
            ],
        )

        store_decision = self.store.decide(
            user_message=user_message,
            assistant_message=response,
        )

        print(f"[Store] {store_decision}")

        self.history.add(
            Message(
                role="assistant",
                content=response,
            )
        )

        return response

    def ask_stream(self, user_message: str):
        """
        Same pipeline and side effects as ``ask``, but for a CHAT-type
        reply, yields the response as incremental text deltas as the
        model generates them instead of waiting for the full reply.

        Non-CHAT actions (a declined action, or a tool/action that ran)
        have no LLM call to stream in the first place — they're
        already fully-formed strings — so this yields that single
        string as one chunk and stops, matching what ``ask`` would
        return for the same input.

        History/memory-store side effects happen at the very end, once
        the full reply is known, exactly as in ``ask``.
        """

        pending_response = self._handle_pending_confirmation(user_message)

        if pending_response is not None:
            yield pending_response
            return

        recall_result, action, plan, reasoning = self._run_pipeline(
            user_message,
        )

        non_chat_response = self._run_non_chat_action(
            user_message, action, plan, reasoning,
        )

        if non_chat_response is not None:
            yield non_chat_response
            return

        response_parts: list[str] = []

        for chunk in self.brain.think_stream(
            history=self.history,
            user_message=user_message,
            memories=[
                result.memory.content
                for result in recall_result.memories
            ],
        ):
            response_parts.append(chunk)
            yield chunk

        response = "".join(response_parts)

        store_decision = self.store.decide(
            user_message=user_message,
            assistant_message=response,
        )

        print(f"[Store] {store_decision}")

        self.history.add(
            Message(
                role="assistant",
                content=response,
            )
        )
