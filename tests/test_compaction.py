"""Tests for conversation compaction (long-session memory).

The decision/formatting logic is pure. The two Brain tests swap in a stub
AI, so nothing here calls a real model or the network.
"""

from __future__ import annotations

from src.modules.brain.context import ContextBuilder
from src.modules.brain.manager import Brain
from src.modules.conversation.compaction import (
    build_compaction_messages,
    needs_compaction,
    split_for_compaction,
)
from src.modules.conversation.history import ConversationHistory
from src.modules.conversation.message import Message
from src.modules.identity.manager import IdentityManager


def _history(count: int) -> ConversationHistory:
    history = ConversationHistory()
    for index in range(count):
        history.add(
            Message(
                role="user" if index % 2 == 0 else "assistant",
                content=f"message {index}",
            )
        )
    return history


class _StubAI:
    """Stands in for the model so the Brain tests stay offline."""

    def __init__(self, reply: str = "A summary.", fail: bool = False) -> None:
        self.reply = reply
        self.fail = fail
        self.calls: list[list[dict]] = []

    def chat(self, messages: list[dict]) -> str:
        self.calls.append(messages)
        if self.fail:
            raise RuntimeError("model unavailable")
        return self.reply


# --- decision logic ----------------------------------------------------


def test_needs_compaction_only_past_the_limit():
    assert not needs_compaction(40, 40)
    assert needs_compaction(41, 40)


def test_split_keeps_the_most_recent_verbatim():
    messages = [Message(role="user", content=f"m{i}") for i in range(10)]

    older, recent = split_for_compaction(messages, 4)

    assert [m.content for m in older] == [f"m{i}" for i in range(6)]
    assert [m.content for m in recent] == ["m6", "m7", "m8", "m9"]


def test_split_with_zero_keep_last_keeps_nothing_verbatim():
    # messages[:-0] is [], not the whole list — the guard matters.
    messages = [Message(role="user", content=f"m{i}") for i in range(5)]

    older, recent = split_for_compaction(messages, 0)

    assert len(older) == 5
    assert recent == []


def test_split_when_history_is_shorter_than_keep_last():
    messages = [Message(role="user", content="only one")]

    older, recent = split_for_compaction(messages, 12)

    assert older == []
    assert len(recent) == 1


def test_compaction_prompt_includes_the_transcript():
    older = [
        Message(role="user", content="what is the solar system"),
        Message(role="assistant", content="the sun and everything orbiting it"),
    ]

    messages = build_compaction_messages(older)

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "user: what is the solar system" in messages[1]["content"]
    assert "assistant: the sun and everything orbiting it" in messages[1]["content"]


def test_compaction_prompt_carries_a_previous_summary_forward():
    messages = build_compaction_messages(
        [Message(role="user", content="and Mars?")],
        previous_summary="They were discussing planets.",
    )

    assert "They were discussing planets." in messages[1]["content"]


# --- history -----------------------------------------------------------


def test_history_summary_starts_empty():
    assert ConversationHistory().summary == ""


def test_apply_compaction_sets_the_summary_and_trims_messages():
    history = _history(10)
    recent = history.messages()[-4:]

    history.apply_compaction("They talked about the weather.", recent)

    assert history.summary == "They talked about the weather."
    assert len(history.messages()) == 4
    assert history.messages()[-1].content == "message 9"


def test_clear_also_drops_the_summary():
    history = _history(3)
    history.apply_compaction("old stuff", [])

    history.clear()

    assert history.summary == ""
    assert history.messages() == []


# --- prompt ------------------------------------------------------------


def test_context_includes_the_summary_when_present():
    history = ConversationHistory()
    history.apply_compaction("They discussed the solar system.", [])

    messages = ContextBuilder(identity=IdentityManager()).build(
        history=history,
        memories=[],
    )

    content = messages[0]["content"]
    assert "Earlier in this conversation" in content
    assert "solar system" in content


def test_context_has_no_summary_section_when_empty():
    messages = ContextBuilder(identity=IdentityManager()).build(
        history=ConversationHistory(),
        memories=[],
    )

    assert "Earlier in this conversation" not in messages[0]["content"]


# --- brain wiring ------------------------------------------------------


def test_brain_compacts_a_long_history():
    brain = Brain(
        identity=IdentityManager(),
        max_history_messages=6,
        keep_recent_messages=4,
    )
    brain.ai = _StubAI("A summary.")

    history = _history(10)
    brain._compact_history(history)

    assert history.summary == "A summary."
    assert len(history.messages()) == 4
    assert history.messages()[-1].content == "message 9"
    assert len(brain.ai.calls) == 1


def test_brain_leaves_a_short_history_alone():
    brain = Brain(
        identity=IdentityManager(),
        max_history_messages=40,
        keep_recent_messages=12,
    )
    brain.ai = _StubAI("A summary.")

    history = _history(10)
    brain._compact_history(history)

    assert history.summary == ""
    assert len(history.messages()) == 10
    assert brain.ai.calls == []


def test_brain_survives_a_failing_summary():
    brain = Brain(
        identity=IdentityManager(),
        max_history_messages=6,
        keep_recent_messages=4,
    )
    brain.ai = _StubAI(fail=True)

    history = _history(10)
    brain._compact_history(history)  # must not raise

    assert history.summary == ""
    assert len(history.messages()) == 10
