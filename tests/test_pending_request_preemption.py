"""What happens when you ask something new mid-confirmation.

The bug these pin down, from the logs: EON asked for a yes/no before a
*weather* question, the user answered with something else, and EON
re-prompted. And re-prompted. One unanswered question blocked every
later request — music, the same question again, anything — until the
user worked out they had to say "no" to a question they had already
stopped caring about.

Two separate faults, so two separate things to hold:

    1. A harmless read-only action asked at all. WEATHER was missing
       from the auto-approved list while CALENDAR_READ and EMAIL_READ
       were on it.
    2. A new request did not outrank a pending one.

The second is the fix with the sharp edge, so it gets the most tests:
dropping a pending action must clear it, must not run it, and must not
disturb a genuine yes or no.
"""

from __future__ import annotations

from src.modules.actions.models import Action, ActionType
from src.modules.conversation.manager import ConversationManager
from src.modules.permissions.config import (
    DEFAULT_AUTO_ACTION_TYPES,
    PermissionsServiceConfig,
)
from src.modules.permissions.manager import PermissionManager
from src.modules.permissions.models import ConfirmationOutcome, PermissionLevel
from src.modules.planner.models import Goal, Plan, Step


def _plan(action_type: ActionType, target: str = "something") -> Plan:
    """A one-step plan, which is all the permission layer looks at."""
    return Plan(
        goal=Goal(description=target),
        steps=[Step(action=Action(type=action_type, target=target))],
    )


def _manager() -> PermissionManager:
    return PermissionManager(config=PermissionsServiceConfig())


# --- 1. harmless actions should not ask ------------------------------------


def test_a_weather_question_does_not_ask_for_confirmation():
    """The exact case from the logs."""
    manager = _manager()

    level = manager.classify(_plan(ActionType.WEATHER, "do I need an umbrella"))

    assert level is PermissionLevel.AUTO


def test_weather_is_on_the_auto_approved_list():
    assert ActionType.WEATHER in DEFAULT_AUTO_ACTION_TYPES


def test_the_other_read_only_actions_are_still_auto():
    """So a later change can't quietly re-gate them."""
    for action_type in (
        ActionType.SEARCH_WEB,
        ActionType.CALENDAR_READ,
        ActionType.EMAIL_READ,
        ActionType.CLIPBOARD_READ,
        ActionType.MUSIC,
    ):
        assert action_type in DEFAULT_AUTO_ACTION_TYPES, action_type


def test_closing_a_window_still_asks():
    """WINDOW_CONTROL is deliberately *not* auto-approved.

    It looks as harmless as VOLUME_CONTROL, but it can close a window —
    and closing one can lose whatever was unsaved in it. So it keeps
    asking. This is here so that tidying up the auto list later can't
    quietly widen it.
    """
    manager = _manager()

    assert ActionType.WINDOW_CONTROL not in DEFAULT_AUTO_ACTION_TYPES
    assert manager.classify(_plan(ActionType.WINDOW_CONTROL)) is not PermissionLevel.AUTO


# --- 2. dropping a pending action ------------------------------------------


def test_dropping_a_pending_action_clears_it():
    manager = _manager()
    manager.request(_plan(ActionType.EMAIL_SEND, "email dad"))
    assert manager.has_pending()

    dropped = manager.discard()

    assert dropped is not None
    assert not manager.has_pending(), "the action must not still be waiting"


def test_dropping_nothing_is_harmless():
    assert _manager().discard() is None


def test_a_dropped_action_never_runs():
    """The safety property that makes dropping the right direction."""
    manager = _manager()
    manager.request(_plan(ActionType.RUN_COMMAND, "rm -rf /"))

    manager.discard()

    # Resolving afterwards must find nothing to resolve.
    outcome, pending = manager.resolve("yes")

    assert outcome is ConfirmationOutcome.NOT_A_RESPONSE
    assert pending is None


# --- and a real answer is still a real answer ------------------------------


def test_a_plain_yes_still_resolves_the_pending_action():
    manager = _manager()
    manager.request(_plan(ActionType.EMAIL_SEND, "email dad"))

    outcome, pending = manager.resolve("yes")

    assert outcome is ConfirmationOutcome.CONFIRMED
    assert pending is not None
    assert not manager.has_pending()


def test_a_plain_no_still_resolves_the_pending_action():
    manager = _manager()
    manager.request(_plan(ActionType.EMAIL_SEND, "email dad"))

    outcome, pending = manager.resolve("no")

    assert outcome is ConfirmationOutcome.DENIED
    assert pending is not None


# --- 3. and the conversation path that ties them together ------------------


class _StubHistory:
    """Records what was said, so the answer paths have somewhere to write."""

    def __init__(self) -> None:
        self.messages: list = []

    def add(self, message) -> None:
        self.messages.append(message)


class _StubPermissions:
    """A permission manager that is always mid-confirmation."""

    def __init__(self, outcome: ConfirmationOutcome) -> None:
        self._outcome = outcome
        self.discarded = 0

    def has_pending(self) -> bool:
        return True

    def resolve(self, user_message: str):
        return self._outcome, object()

    def discard(self):
        self.discarded += 1
        return object()


def _conversation(permissions) -> ConversationManager:
    """Only ``permissions`` and ``history`` are used on this path."""
    return ConversationManager(
        history=_StubHistory(),
        brain=None,
        perception=None,
        context=None,
        recall=None,
        store=None,
        intent=None,
        planner=None,
        reasoning=None,
        router=None,
        execution=None,
        monitor=None,
        reflection=None,
        permissions=permissions,
        memory=None,
    )


def test_a_new_request_drops_the_pending_action_and_is_handled_normally():
    """Returning None is what sends the message on to the normal
    pipeline — so the user gets an answer to what they actually asked."""
    permissions = _StubPermissions(ConfirmationOutcome.NOT_A_RESPONSE)
    manager = _conversation(permissions)

    result = manager._handle_pending_confirmation("what's the weather like")

    assert result is None, "the message must fall through, not be answered with a prompt"
    assert permissions.discarded == 1, "the stale action must be dropped"


def test_a_real_answer_is_still_handled_as_an_answer():
    """Only the non-answer path changed."""
    permissions = _StubPermissions(ConfirmationOutcome.DENIED)
    manager = _conversation(permissions)

    result = manager._handle_pending_confirmation("no")

    assert result == "Okay, cancelled."
    assert permissions.discarded == 0
