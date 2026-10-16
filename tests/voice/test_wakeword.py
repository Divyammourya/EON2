"""Tests for wake-word matching (exact + fuzzy).

Constructing ``WakeWordListener`` does no I/O, so the matching helpers
can be exercised directly with placeholder collaborators.
"""

from __future__ import annotations

from src.modules.voice.wakeword import WakeWordListener, _levenshtein


def _listener(wake_word: str = "eon") -> WakeWordListener:
    return WakeWordListener(
        microphone=None,  # type: ignore[arg-type]
        manager=None,  # type: ignore[arg-type]
        mic_lock=None,  # type: ignore[arg-type]
        wake_word=wake_word,
        sample_rate_hz=16_000,
        window_seconds=2.0,
        check_interval_seconds=0.5,
        energy_threshold=300.0,
        on_wake=lambda is_owner: None,
    )


def test_levenshtein_basics():
    assert _levenshtein("eon", "eon") == 0
    assert _levenshtein("eon", "leon") == 1
    assert _levenshtein("eon", "on") == 1


def test_exact_wake_word_matches():
    assert _listener()._fuzzy_wake_word_match("eon") is True


def test_close_mishearing_matches():
    assert _listener()._fuzzy_wake_word_match("leon") is True


def test_short_common_words_no_longer_trigger():
    # "on" / "an" are within edit distance 1 of "eon" but are common
    # words — they must not wake EON.
    listener = _listener()
    assert listener._fuzzy_wake_word_match("on") is False
    assert listener._fuzzy_wake_word_match("an") is False


def test_unrelated_speech_does_not_trigger():
    listener = _listener()
    assert listener._fuzzy_wake_word_match("turn on the lights") is False
    assert listener._fuzzy_wake_word_match("thank you") is False
    assert listener._fuzzy_wake_word_match("what is the time") is False


def test_wake_word_inside_a_sentence_matches():
    assert _listener()._fuzzy_wake_word_match("hello eon are you there") is True


def test_configurable_longer_wake_word():
    listener = _listener(wake_word="jarvis")
    assert listener._fuzzy_wake_word_match("jarvis") is True
    assert listener._fuzzy_wake_word_match("jarvis please") is True
    assert listener._fuzzy_wake_word_match("service") is False
