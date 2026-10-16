"""
Multi-Step Goal Splitter.

Splits a single user message into an ordered list of sub-goal phrases
when it describes more than one distinct task chained together (e.g.
"organize my downloads, then email me a summary"), so each sub-goal
can be classified and routed independently — producing steps with
different action types in one Plan, rather than the one-action-per-turn
behavior EON had before.

Deliberately separate from ``GoalDecomposer``, which splits text for a
*single already-classified* action (e.g. "open chrome and spotify" —
one OPEN_APP intent, multiple targets, same action type for every
step). This splitter runs *before* intent classification instead,
since chained sub-goals may each need a completely different action
type — decomposing "organize my downloads, then email me a summary"
requires classifying each half on its own.
"""

from __future__ import annotations

import re

# Connectors that signal "do this, then do that" — deliberately a
# short, unambiguous list. A broader list (e.g. plain "and") would
# collide with GoalDecomposer's existing same-action-type splitting
# and with ordinary sentences that just happen to contain "and".
#
# "uske baad" and "phir" each optionally swallow a leading "aur"
# ("and") via the non-capturing `(?:\baur\s+)?` group, since Hinglish
# speakers commonly say "aur uske baad"/"aur phir" as one connector
# ("...karo aur uske baad chrome open karo"). Without that, a bare
# "uske baad"/"phir" match would leave a dangling "aur" stuck to the
# end of the previous sub-goal.
_CHAIN_PATTERN = re.compile(
    r",?\s*\bthen\b\s*"
    r"|\bafter that\b\s*,?\s*"
    r"|;\s*"
    r"|,?\s*(?:\baur\s+)?\buske baad\b\s*"
    r"|,?\s*(?:\baur\s+)?\bphir\b\s*",
    re.IGNORECASE,
)


class MultiStepSplitter:
    """Splits chained natural-language requests into ordered sub-goals."""

    def split(self, text: str) -> list[str]:
        """Splits ``text`` on chaining connectors ("then", "after
        that", ";"), returning one sub-goal phrase per detected step,
        in order.

        Returns a single-item list containing the original (stripped)
        text unchanged if no chaining connector is found, so callers
        can treat the return value uniformly instead of branching on
        "was this actually multi-step".
        """
        stripped = text.strip()

        if not stripped:
            return [stripped]

        parts = _CHAIN_PATTERN.split(stripped)

        sub_goals = [
            cleaned
            for part in parts
            if (cleaned := part.strip(" ,;")) and any(ch.isalnum() for ch in cleaned)
        ]

        return sub_goals or [stripped]
