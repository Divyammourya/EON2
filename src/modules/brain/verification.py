"""Checking a claim against the evidence it was drawn from.

Tier 2, first piece. When EON grounds an answer in web results, the model
still writes the prose — and a 3B model will happily state things the
results do not say. So after the answer is generated, one short extra
call asks the only question that matters:

    does the evidence above support every claim in this answer?

This is the cheapest anti-hallucination measure available at this size.
It is not a fact-checker and it cannot tell whether the *sources* are
right; it only catches the model going beyond what it was given, which
is the failure that actually shows up in use.

Three verdicts, and the distinction between them matters:

    SUPPORTED    the checker said so, cleanly.
    UNSUPPORTED  the checker said a claim is not backed.
    UNKNOWN      the checker did not answer usefully, or failed.

Only UNSUPPORTED changes the reply. UNKNOWN is logged and otherwise
ignored, deliberately: it means the *check* did not work, not that the
answer is wrong, and hedging every answer because a small model waffled
at a yes/no question would make EON sound unsure of everything — which
is its own kind of dishonesty.
"""

from __future__ import annotations

from enum import Enum

from src.core.logger import get_logger
from src.modules.ai.manager import AIManager
from src.modules.tools.knowledge.web_search import WebPassage, format_grounding

logger = get_logger("Verification")


class Verdict(Enum):
    """What the checker said about an answer."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


#: Said to the model before the evidence. Written for a small model:
#: one decision, one word, no room to explain.
_SYSTEM = (
    "You check whether an answer is supported by evidence. "
    "Reply with exactly one word: SUPPORTED if every claim in the answer "
    "is backed by the evidence, or UNSUPPORTED if any claim is not. "
    "Never explain. Never apologise. Never add punctuation."
)

#: What the answer is prefixed with when the checker says a claim in it
#: is not backed by the sources EON found.
UNSUPPORTED_PREFIX = "I'm not fully sure about this, but: "


class Verifier:
    """Asks whether an answer went beyond its evidence.

    Attributes:
        enabled: Whether it will do anything at all.
    """

    def __init__(
        self,
        ai: AIManager | None = None,
        *,
        enabled: bool | None = None,
    ) -> None:
        """Builds the verifier.

        Args:
            ai: The AI manager to ask. Defaults to a new one, which
                uses the shared provider.
            enabled: Whether to consult the model at all. ``None``
                means read ``verification_enabled`` from the
                configuration, defaulting to on.
        """
        self._ai = ai
        self._explicit_enabled = enabled

    @property
    def enabled(self) -> bool:
        """Whether the model will be consulted."""
        if self._explicit_enabled is not None:
            return self._explicit_enabled

        return _configured_enabled()

    def check(
        self,
        answer: str,
        evidence: list[WebPassage],
    ) -> Verdict:
        """Asks whether ``answer`` is supported by ``evidence``.

        Never raises, and never consults the model when there is nothing
        to check: an answer with no evidence behind it, or an empty
        answer, comes back ``UNKNOWN`` without a call.

        Args:
            answer: What EON is about to say.
            evidence: The passages it was grounded in.

        Returns:
            A ``Verdict``.
        """
        if not self.enabled:
            return Verdict.UNKNOWN

        if not answer or not answer.strip():
            return Verdict.UNKNOWN

        if not evidence:
            return Verdict.UNKNOWN

        if self._ai is None:
            self._ai = AIManager()

        try:
            reply = self._ai.chat(self._build_messages(answer, evidence))
        except Exception as error:
            logger.warning("Verification failed, leaving the answer alone: %s", error)
            return Verdict.UNKNOWN

        return self._interpret(reply)

    @staticmethod
    def _interpret(reply: str) -> Verdict:
        """Reads the checker's one word.

        ``UNSUPPORTED`` is tested first, and that order is the whole
        point: it *contains* ``SUPPORTED``, so a naive check for
        ``SUPPORTED`` would read "UNSUPPORTED" as a pass — which is the
        one mistake this class must not make, because it would wave
        through exactly the answers it exists to catch.

        Args:
            reply: Whatever the model said.

        Returns:
            A ``Verdict``; anything unclear is ``UNKNOWN``.
        """
        if not reply:
            return Verdict.UNKNOWN

        text = reply.strip().upper()

        if "UNSUPPORTED" in text:
            return Verdict.UNSUPPORTED

        if "SUPPORTED" in text:
            return Verdict.SUPPORTED

        return Verdict.UNKNOWN

    @staticmethod
    def _build_messages(
        answer: str,
        evidence: list[WebPassage],
    ) -> list[dict]:
        """The prompt: the evidence, then the answer, then the question."""
        return [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    f"{format_grounding(evidence)}\n\n"
                    f"Answer:\n{answer}\n\n"
                    "One word:"
                ),
            },
        ]


def hedged(answer: str, verdict: Verdict) -> str:
    """The answer as it should be said, given the verdict.

    Args:
        answer: What the model wrote.
        verdict: What the checker said.

    Returns:
        The answer, prefixed when a claim in it was not backed by the
        sources. ``SUPPORTED`` and ``UNKNOWN`` leave it untouched.
    """
    if verdict is not Verdict.UNSUPPORTED:
        return answer

    return f"{UNSUPPORTED_PREFIX}{answer}"


def _configured_enabled() -> bool:
    """Reads ``verification_enabled`` from the configuration.

    Read once per call rather than cached, so flipping the setting and
    restarting is enough. A missing key, or a configuration that can't
    be loaded, means on: this is a correctness feature, so its absence
    should not silently disable it.

    Returns:
        Whether verification should run.
    """
    try:
        from src.core.config import ConfigManager

        value = ConfigManager().get("verification_enabled")
    except Exception as error:
        logger.debug("Could not read verification_enabled: %s", error)
        return True

    if value is None:
        return True

    return bool(value)
