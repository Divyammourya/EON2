"""The verifier, as the Brain actually uses it.

The unit tests cover the check in isolation. These cover the wiring: that
a grounded answer gets checked, that an ungrounded one does not, and that
the hedge is in place before the user hears anything — including on the
streaming path, where the answer is buffered rather than passed through
as it arrives.
"""

from __future__ import annotations

from src.modules.brain.manager import Brain
from src.modules.brain.verification import UNSUPPORTED_PREFIX, Verdict
from src.modules.tools.knowledge.web_search import WebPassage


def _passages() -> list[WebPassage]:
    return [
        WebPassage(
            title="Canada",
            snippet="Canada is a country in North America.",
            url="https://example.org/canada",
        )
    ]


class _StubHistory:
    summary = ""

    def messages(self) -> list:
        return []

    def to_ollama(self) -> list:
        return []


class _StubIdentity:
    def system_prompt(self) -> str:
        return "You are EON."


class _StubKnowledge:
    def __init__(self, passages: list[WebPassage]) -> None:
        self.passages = passages

    def grounding_for(self, message: str) -> list[WebPassage]:
        return self.passages


class _StubSkills:
    def answer(self, message: str):
        return None


class _StubAI:
    def __init__(self, reply: str = "Canada is in North America.") -> None:
        self.reply = reply

    def chat(self, messages: list[dict]) -> str:
        return self.reply

    def chat_stream(self, messages: list[dict]):
        yield self.reply


class _StubVerifier:
    def __init__(self, verdict: Verdict) -> None:
        self.verdict = verdict
        self.calls = 0
        self.evidence: list[WebPassage] = []

    def check(self, answer: str, evidence: list[WebPassage]) -> Verdict:
        self.calls += 1
        self.evidence = evidence
        return self.verdict


def _brain(passages: list[WebPassage]) -> Brain:
    return Brain(
        identity=_StubIdentity(),
        knowledge=_StubKnowledge(passages),
        skills=_StubSkills(),
    )


# --- 1. a grounded answer is checked, and hedged if it went too far -------


def test_an_answer_beyond_its_evidence_is_hedged():
    brain = _brain(_passages())
    brain.ai = _StubAI("Canada is the largest country in the world.")
    brain.verifier = _StubVerifier(Verdict.UNSUPPORTED)

    answer = brain.think(_StubHistory(), "where is canada", [])

    assert answer.startswith(UNSUPPORTED_PREFIX)
    assert "largest country" in answer


def test_a_supported_answer_is_returned_untouched():
    brain = _brain(_passages())
    brain.ai = _StubAI("Canada is in North America.")
    brain.verifier = _StubVerifier(Verdict.SUPPORTED)

    answer = brain.think(_StubHistory(), "where is canada", [])

    assert answer == "Canada is in North America."


def test_the_checker_is_given_the_evidence():
    brain = _brain(_passages())
    brain.ai = _StubAI()
    verifier = _StubVerifier(Verdict.SUPPORTED)
    brain.verifier = verifier

    brain.think(_StubHistory(), "where is canada", [])

    assert verifier.calls == 1
    assert verifier.evidence == _passages()


# --- 2. and is not asked when there is nothing to check against -----------


def test_an_ungrounded_answer_is_not_checked():
    brain = _brain([])
    brain.ai = _StubAI("Hello, sir.")
    verifier = _StubVerifier(Verdict.SUPPORTED)
    brain.verifier = verifier

    answer = brain.think(_StubHistory(), "hi", [])

    assert answer == "Hello, sir."
    assert verifier.calls == 0, "nothing to check against, so nothing to ask"


# --- 3. the streaming path hedges too, before the user hears anything -----


def test_streaming_hedges_before_yielding():
    """The answer is buffered rather than passed through, so the hedge
    is in place in the very first chunk the user sees or hears."""
    brain = _brain(_passages())
    brain.ai = _StubAI("Canada is the largest country in the world.")
    brain.verifier = _StubVerifier(Verdict.UNSUPPORTED)

    chunks = list(brain.think_stream(_StubHistory(), "where is canada", []))

    assert chunks, "something must be yielded"
    assert chunks[0].startswith(UNSUPPORTED_PREFIX)
    assert all(
        UNSUPPORTED_PREFIX not in chunk[1:] for chunk in chunks
    ), "the hedge must appear once, at the start"


def test_streaming_leaves_a_supported_answer_alone():
    brain = _brain(_passages())
    brain.ai = _StubAI("Canada is in North America.")
    brain.verifier = _StubVerifier(Verdict.SUPPORTED)

    chunks = list(brain.think_stream(_StubHistory(), "where is canada", []))

    assert "".join(chunks) == "Canada is in North America."
