"""Local skills: the things EON answers itself, without the model.

Some questions have exactly one right answer — arithmetic, unit
conversions, "what's on my shopping list". A 3B model asked any of those
will produce something confident and wrong, and there is no reason to
involve it at all.

``LocalSkills.answer`` gives those a chance to answer first. Anything it
doesn't recognise returns ``None`` and the turn carries on to the model
exactly as before, so this can only ever add correct answers — it can't
take away the model's ability to answer everything else.

Requires: Python 3.12+
"""

from __future__ import annotations

from src.modules.tools.utility import calculator, lists, units
from src.modules.tools.utility.lists import ListStore


class LocalSkills:
    """Deterministic answers for the questions a model gets wrong."""

    def __init__(
        self,
        store: ListStore | None = None,
        enabled: bool = True,
    ) -> None:
        self._store = store if store is not None else ListStore()
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        """Whether local skills are switched on."""
        return self._enabled

    def answer(self, text: str) -> str | None:
        """Returns a direct answer for ``text``, or None.

        Order matters: list commands run first because they can contain
        arithmetic-looking text — "add 2 kg of rice to my shopping list"
        is a list command, not a calculation.
        """
        if not self._enabled or not text.strip():
            return None

        reply = lists.handle(text, self._store)

        if reply is not None:
            return reply

        for skill in (calculator.answer, units.answer):
            reply = skill(text)

            if reply is not None:
                return reply

        return None
