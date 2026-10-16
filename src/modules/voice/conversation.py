"""Conversation-mode helpers for the EON Voice module.

Currently this holds the exit-phrase check that decides when a
continuous voice conversation should end and EON should go back to
waiting for the wake word.

Kept pure (stdlib only) so it can be unit tested directly, with no
microphone, provider, or session involved.
"""

from __future__ import annotations

import re

from collections.abc import Iterable

# Leading words people commonly say before an actual command/phrase
# ("okay, that's all", "alright, goodbye"). Stripping a short lead-in
# lets those still register as the phrase underneath, without making
# the match so loose that real commands match by accident.
_LEAD_IN_WORDS = frozenset(
    {"ok", "okay", "alright", "allright", "so", "well", "and", "then", "yeah", "yes"}
)

# At most this many leading words are treated as filler before the
# phrase check. Keeps "stop the music" from ever matching a "stop"
# style phrase, since only the first two words can be skipped.
_MAX_LEAD_IN_WORDS = 2


def _normalize(text: str) -> str:
    """Lowercases and strips punctuation/extra whitespace from ``text``."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_exit_phrase(text: str, phrases: Iterable[str]) -> bool:
    """Whether ``text`` is (or ends with) one of the exit phrases.

    Matching is deliberately strict rather than substring-based: the
    normalized text must *equal* a phrase, optionally preceded by at
    most two filler words. So "goodbye" and "okay, that's all" match,
    but "stop the music" does not match a "stop" phrase and "i'm done
    with the report" does not match "i'm done".

    Args:
        text: The (possibly noisy) transcript to check.
        phrases: The exit phrases to match against.

    Returns:
        ``True`` if the text should end the conversation.
    """
    normalized = _normalize(text)
    if not normalized:
        return False

    normalized_phrases = {_normalize(phrase) for phrase in phrases}
    normalized_phrases.discard("")

    if normalized in normalized_phrases:
        return True

    words = normalized.split()
    limit = min(len(words) - 1, _MAX_LEAD_IN_WORDS)
    for start in range(1, limit + 1):
        if words[start - 1] not in _LEAD_IN_WORDS:
            # Only skip a leading word if it is actual filler; otherwise
            # stop, so we never skip past a meaningful word.
            break
        if " ".join(words[start:]) in normalized_phrases:
            return True

    return False
