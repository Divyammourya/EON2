"""Tests for where the tool fallback is plugged in.

The fallback must fire on exactly one condition — the keyword rules came
back with CHAT — and its answer must go through ``ActionRouter`` like
any other, so the permission layer still gets its say. Both of those are
easy to get subtly wrong, and neither would show up until something
dangerous ran without asking.
"""

from __future__ import annotations

import inspect

from src.modules.actions.models import Action, ActionType
from src.modules.actions.router import ActionRouter
from src.modules.conversation.manager import ConversationManager
from src.modules.intent.models import Intent, IntentType


class _StubIntent:
    """Stands in for IntentManager: returns whatever it was told to."""

    def __init__(self, intent: Intent) -> None:
        self._intent = intent
        self.seen: list[str] = []

    def detect(self, text: str) -> Intent:
        self.seen.append(text)
        return self._intent


class _StubRouter:
    """Stands in for ActionRouter: records what it was asked to route."""

    def __init__(self) -> None:
        self.routed: list[IntentType] = []

    def route(self, intent: Intent) -> Action:
        self.routed.append(intent.type)
        return Action(type=ActionType(intent.type.value), target=intent.target)


class _StubToolRouter:
    """Stands in for ToolRouter: returns a fixed answer, or nothing."""

    def __init__(self, chosen: Intent | None = None) -> None:
        self._chosen = chosen
        self.asked: list[str] = []

    def choose(self, text: str) -> Intent | None:
        self.asked.append(text)
        return self._chosen


def _manager(intent: Intent, tool_router=None) -> ConversationManager:
    """A manager with only the pieces ``_detect_action`` touches.

    Everything else in the constructor is stored and never called, so
    None is fine for it.
    """
    manager = ConversationManager(
        history=None,
        brain=None,
        perception=None,
        context=None,
        recall=None,
        store=None,
        intent=_StubIntent(intent),
        planner=None,
        reasoning=None,
        router=_StubRouter(),
        execution=None,
        monitor=None,
        reflection=None,
        permissions=None,
        memory=None,
        tool_router=tool_router,
    )
    return manager


def test_the_constructor_accepts_a_router_so_a_test_can_supply_one():
    parameter = inspect.signature(ConversationManager.__init__).parameters["tool_router"]

    assert parameter.default is None


# --- when it fires ----------------------------------------------------------


def test_an_unmatched_message_is_offered_to_the_model():
    tool_router = _StubToolRouter(Intent(IntentType.WEATHER, target="will it rain"))
    manager = _manager(Intent(IntentType.CHAT, target="will it rain"), tool_router)

    manager._detect_action("will it rain")

    assert tool_router.asked == ["will it rain"]


def test_a_message_the_rules_understood_is_never_sent_to_the_model():
    """The keyword path is the fast one; it must stay untouched."""
    tool_router = _StubToolRouter(Intent(IntentType.WEATHER, target="x"))
    manager = _manager(Intent(IntentType.OPEN_APP, target="notepad"), tool_router)

    manager._detect_action("open notepad")

    assert tool_router.asked == []


# --- what happens with the answer -------------------------------------------


def test_a_tool_the_model_picked_is_used():
    tool_router = _StubToolRouter(Intent(IntentType.WEATHER, target="will it rain"))
    manager = _manager(Intent(IntentType.CHAT, target="will it rain"), tool_router)

    action = manager._detect_action("will it rain")

    assert action.type is ActionType.WEATHER


def test_the_chosen_tool_still_goes_through_the_router():
    """Which is what puts it in front of the permission layer."""
    tool_router = _StubToolRouter(Intent(IntentType.EMAIL_SEND, target="email dad"))
    manager = _manager(Intent(IntentType.CHAT, target="email dad"), tool_router)

    manager._detect_action("email dad")

    assert manager.router.routed == [IntentType.EMAIL_SEND]


def test_nothing_chosen_leaves_the_message_as_chat():
    tool_router = _StubToolRouter(None)
    manager = _manager(Intent(IntentType.CHAT, target="why is the sky blue"), tool_router)

    action = manager._detect_action("why is the sky blue")

    assert action.type is ActionType.CHAT
    assert manager.router.routed == [IntentType.CHAT]


def test_a_learned_phrase_is_still_answered_from_memory_first():
    """The fallback must not get in front of a phrase EON was taught."""

    class _Memory:
        def get_learned_phrase(self, text):
            return ("open_app", "notepad")

    tool_router = _StubToolRouter(Intent(IntentType.WEATHER, target="x"))
    manager = _manager(Intent(IntentType.CHAT, target="notepad"), tool_router)
    manager.memory = _Memory()

    action = manager._detect_action("notepad")

    assert action.type is ActionType.OPEN_APP
    assert tool_router.asked == [], "the learned phrase should win outright"


# --- the real router, wired in ----------------------------------------------


def test_the_real_router_is_built_on_first_use_and_then_reused():
    """So a session that never misses never pays for an AI provider."""
    manager = _manager(Intent(IntentType.CHAT, target="x"), None)

    assert manager._tool_router is None, "not built yet"

    first = manager.tool_router

    assert first is manager.tool_router, "and only built once"
