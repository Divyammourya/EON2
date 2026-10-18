"""Checking an answer against its evidence.

Tier 2, first piece. The failure this exists to catch is not "the sources
were wrong" — it is "the model went further than the sources", which is
what a 3B model does whenever it is asked something it only half knows.

The important tests here are the ones about *not* being fooled:

    - ``UNSUPPORTED`` contains ``SUPPORTED``. Read in the wrong order,
      the checker would pass exactly the answers it exists to catch, so
      that ordering has a test of its own.
    - Anything unclear is UNKNOWN, never SUPPORTED. Failing towards
      "I don't know" is the whole point.
    - Only UNSUPPORTED changes the reply. UNKNOWN means the *check*
      failed, not that the answer is wrong, and hedging on it would make
      EON sound unsure of everything.
"""

from __future__ import annotations

import pytest

from src.modules.brain.verification import (
    UNSUPPORTED_PREFIX,
    Verdict,
    Verifier,
    hedged,
)
from src.modules.tools.knowledge.web_search import WebPassage


def _passages() -> list[WebPassage]:
    return [
        WebPassage(
            title="Canada",
            snippet="Canada is a country in North America.",
            url="https://example.org/canada",
        )
    ]


class _StubAI:
    """Answers with a fixed reply, or raises if told to."""

    def __init__(self, reply: str = "SUPPORTED", error: bool = False) -> None:
        self.reply = reply
        self.error = error
        self.calls = 0

    def chat(self, messages: list[dict]) -> str:
        self.calls += 1

        if self.error:
            raise RuntimeError("model unavailable")

        return self.reply


# --- 1. reading the checker's one word ------------------------------------


def test_unsupported_is_not_mistaken_for_supported():
    """The trap: ``UNSUPPORTED`` contains ``SUPPORTED``. A naive check
    would read it as a pass — and pass exactly the answers this exists
    to catch."""
    assert Verifier._interpret("UNSUPPORTED") is Verdict.UNSUPPORTED
    assert Verifier._interpret("unsupported") is Verdict.UNSUPPORTED
    assert Verifier._interpret("UNSUPPORTED.") is Verdict.UNSUPPORTED


def test_a_clean_supported_is_read_as_supported():
    assert Verifier._interpret("SUPPORTED") is Verdict.SUPPORTED


def test_a_reply_that_merely_contains_the_word_still_works():
    assert Verifier._interpret("The answer is supported.") is Verdict.SUPPORTED


@pytest.mark.parametrize(
    "reply",
    ["", "   ", "I am not sure", "yes", "maybe", "42"],
)
def test_anything_unclear_is_unknown_never_supported(reply):
    """Failing towards "I don't know" is the point."""
    assert Verifier._interpret(reply) is Verdict.UNKNOWN


# --- 2. when it does and does not run -------------------------------------


def test_a_failing_check_never_raises():
    """A broken check must leave EON behaving exactly as it did before."""
    ai = _StubAI(error=True)
    verifier = Verifier(ai=ai, enabled=True)

    assert verifier.check("anything", _passages()) is Verdict.UNKNOWN


def test_an_answer_with_no_evidence_is_not_checked():
    ai = _StubAI()
    verifier = Verifier(ai=ai, enabled=True)

    assert verifier.check("anything", []) is Verdict.UNKNOWN
    assert ai.calls == 0, "nothing to check against, so nothing to ask"


def test_an_empty_answer_is_not_checked():
    ai = _StubAI()
    verifier = Verifier(ai=ai, enabled=True)

    assert verifier.check("", _passages()) is Verdict.UNKNOWN
    assert ai.calls == 0


def test_disabling_it_means_no_call_at_all():
    ai = _StubAI()
    verifier = Verifier(ai=ai, enabled=False)

    assert verifier.check("anything", _passages()) is Verdict.UNKNOWN
    assert ai.calls == 0


def test_a_grounded_answer_is_checked_once():
    ai = _StubAI(reply="SUPPORTED")
    verifier = Verifier(ai=ai, enabled=True)

    assert verifier.check("Canada is in North America.", _passages()) is Verdict.SUPPORTED
    assert ai.calls == 1


# --- 3. what the user ends up hearing -------------------------------------


def test_an_unsupported_answer_is_hedged():
    result = hedged("Canada is the largest country.", Verdict.UNSUPPORTED)

    assert result.startswith(UNSUPPORTED_PREFIX)
    assert "Canada is the largest country." in result


def test_a_supported_answer_is_left_exactly_as_it_was():
    answer = "Canada is in North America."

    assert hedged(answer, Verdict.SUPPORTED) == answer


def test_an_unknown_verdict_does_not_hedge():
    """Deliberate. UNKNOWN means the check failed, not that the answer
    is wrong — hedging on it would make EON sound unsure of everything
    a small model waffled about."""
    answer = "Canada is in North America."

    assert hedged(answer, Verdict.UNKNOWN) == answer
