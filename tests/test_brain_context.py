"""Tests for the date/time grounding injected into EON's system prompt.

Pure logic, no model, no network.
"""

from __future__ import annotations

from datetime import datetime

from src.modules.brain.context import ContextBuilder, current_datetime_note
from src.modules.conversation.history import ConversationHistory
from src.modules.identity.manager import IdentityManager


def test_note_states_the_exact_date_and_weekday():
    note = current_datetime_note(datetime(2026, 10, 16, 16, 45))
    assert "Friday, 16 October 2026" in note
    assert "16:45" in note


def test_note_tracks_a_different_date():
    # 1 January 2000 was a Saturday.
    note = current_datetime_note(datetime(2000, 1, 1, 9, 5))
    assert "Saturday, 01 January 2000" in note
    assert "09:05" in note


def test_note_tells_the_model_not_to_guess():
    note = current_datetime_note(datetime(2026, 10, 16, 12, 0))
    assert "Never answer those from memory" in note


def test_build_injects_the_date_into_the_system_message():
    builder = ContextBuilder(identity=IdentityManager())
    messages = builder.build(history=ConversationHistory(), memories=[])

    assert messages[0]["role"] == "system"
    content = messages[0]["content"]
    assert "Current date and time" in content
    assert "Today is" in content


def test_build_keeps_the_memories_section():
    builder = ContextBuilder(identity=IdentityManager())
    messages = builder.build(
        history=ConversationHistory(),
        memories=["the user's name is Divyam"],
    )

    content = messages[0]["content"]
    assert "Current date and time" in content
    assert "the user's name is Divyam" in content
