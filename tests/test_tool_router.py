"""Tests for the model-chosen tool fallback.

No Qt, no Ollama: the AI manager is a stub that says whatever the test
wants. What matters here is what the router does with a *bad* answer,
because this runs on the path where chatting is the correct fallback —
a wrong tool is worse than no tool.
"""

from __future__ import annotations

import pytest

from src.modules.intent.models import IntentType
from src.modules.intent.tool_router import (
    NONE,
    TOOL_DESCRIPTIONS,
    ToolRouter,
    _words,
)


class _StubAI:
    """An AI manager that replies with whatever it was told to."""

    def __init__(self, reply: str = "", *, raises: Exception | None = None) -> None:
        self._reply = reply
        self._raises = raises
        self.calls: list[list[dict]] = []

    def chat(self, messages: list[dict]) -> str:
        self.calls.append(messages)

        if self._raises is not None:
            raise self._raises

        return self._reply


def _router(reply: str = "", **kwargs) -> tuple[ToolRouter, _StubAI]:
    ai = kwargs.pop("ai", None) or _StubAI(reply, raises=kwargs.pop("raises", None))
    return ToolRouter(ai=ai, enabled=kwargs.pop("enabled", True), **kwargs), ai


# --- reading the model's answer ---------------------------------------------


def test_a_clear_answer_is_taken():
    router, _ = _router("open_app")

    chosen = router.choose("could you start notepad for me")

    assert chosen is not None
    assert chosen.type is IntentType.OPEN_APP


def test_the_whole_sentence_becomes_the_target():
    """The tools parse the sentence themselves, so they need all of it."""
    router, _ = _router("weather")
    text = "is it going to rain in Delhi tomorrow"

    chosen = router.choose(text)

    assert chosen is not None
    assert chosen.target == text


@pytest.mark.parametrize(
    "reply",
    ["open_app", "OPEN_APP", "Open App.", "open app", "  open_app  ", "open-app"],
)
def test_the_obvious_ways_of_writing_a_name_are_all_understood(reply):
    router, _ = _router(reply)

    chosen = router.choose("start notepad")

    assert chosen is not None and chosen.type is IntentType.OPEN_APP, reply


def test_an_answer_with_an_explanation_attached_still_works():
    router, _ = _router("open_app because the request is to start a program")

    chosen = router.choose("start notepad")

    assert chosen is not None and chosen.type is IntentType.OPEN_APP


# --- and every way of not answering -----------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        NONE,
        "none",
        "NONE",
        "None of these fit.",
        "",
        "   ",
        "I'm not sure.",
        "delete_everything",
        "run_command",
        "ui_click",
        "system",
        "chat",
    ],
)
def test_anything_that_is_not_an_offered_tool_means_no_tool(reply):
    router, _ = _router(reply)

    assert router.choose("what is the meaning of life") is None


def test_a_failure_from_the_model_is_not_an_error_here():
    router, _ = _router(raises=RuntimeError("ollama is not running"))

    assert router.choose("start notepad") is None


def test_a_message_with_nothing_in_it_is_not_sent_to_the_model():
    router, ai = _router("open_app")

    assert router.choose("   ") is None
    assert ai.calls == [], "no point spending a model call on whitespace"


def test_switched_off_means_the_model_is_never_asked():
    router, ai = _router("open_app", enabled=False)

    assert router.choose("start notepad") is None
    assert ai.calls == []


# --- what the model is allowed to choose from -------------------------------


def test_the_prompt_offers_every_tool_in_the_catalogue():
    router, ai = _router("none")

    router.choose("something")

    prompt = " ".join(message["content"] for message in ai.calls[0])

    for intent_type, description in TOOL_DESCRIPTIONS.items():
        assert intent_type.value in prompt
        assert description in prompt


def test_the_prompt_asks_for_one_word_and_nothing_else():
    router, ai = _router("none")

    router.choose("something")

    system = ai.calls[0][0]["content"].lower()

    assert "exactly one tool name" in system
    assert "never explain" in system


@pytest.mark.parametrize(
    "intent_type",
    [
        IntentType.SYSTEM,
        IntentType.UI_CLICK,
        IntentType.UI_TYPE,
        IntentType.UI_LIST_ELEMENTS,
        IntentType.VISION,
        IntentType.FILE,
        IntentType.CHAT,
    ],
)
def test_the_actions_a_model_should_not_choose_are_not_on_offer(intent_type):
    """Running commands and driving the UI are not the model's to pick."""
    assert intent_type not in TOOL_DESCRIPTIONS


def test_the_catalogue_can_be_replaced_for_a_test():
    router, _ = _router("weather", catalogue={IntentType.WEATHER: "the weather"})

    assert router.choose("will it rain") is not None
    # ...and nothing outside it is reachable
    router, _ = _router("open_app", catalogue={IntentType.WEATHER: "the weather"})
    assert router.choose("start notepad") is None


# --- the word splitter ------------------------------------------------------


def test_words_splits_on_everything_that_is_not_a_name_character():
    assert _words("Open App.") == ["open", "app"]
    assert _words("open_app because: it is a program!") == [
        "open_app",
        "because",
        "it",
        "is",
        "a",
        "program",
    ]
    assert _words("") == []
    assert _words("   ,,,  ") == []
