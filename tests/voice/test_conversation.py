"""Tests for conversation-mode exit-phrase detection."""

from __future__ import annotations

from src.modules.voice.conversation import is_exit_phrase

PHRASES = [
    "goodbye",
    "bye",
    "stop listening",
    "that's all",
    "never mind",
    "i'm done",
]


def test_exact_phrase_matches():
    assert is_exit_phrase("goodbye", PHRASES) is True


def test_punctuation_and_case_are_ignored():
    assert is_exit_phrase("Goodbye!", PHRASES) is True
    assert is_exit_phrase("  BYE  ", PHRASES) is True


def test_lead_in_filler_is_tolerated():
    assert is_exit_phrase("okay, that's all", PHRASES) is True
    assert is_exit_phrase("yes stop listening", PHRASES) is True


def test_empty_text_does_not_match():
    assert is_exit_phrase("", PHRASES) is False
    assert is_exit_phrase("   ", PHRASES) is False


def test_phrase_embedded_in_a_real_command_does_not_match():
    # "stop the music" must not match a bare "stop"-style phrase.
    assert is_exit_phrase("stop the music", ["stop"]) is False
    # "i'm done with the report" is a task, not an exit.
    assert is_exit_phrase("i'm done with the report", PHRASES) is False


def test_unrelated_speech_does_not_match():
    assert is_exit_phrase("what is the weather today", PHRASES) is False
