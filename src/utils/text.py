"""
Text utilities.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

_SENTENCE_ENDERS = (".", "!", "?", "\n")


def iter_sentences(chunks: Iterable[str]) -> Iterator[str]:
    """
    Groups a stream of small text deltas into complete sentences.

    Meant for LLM streaming output: individual tokens or word
    fragments arrive one at a time, but speaking (or printing) a
    whole sentence at once reads far more naturally than a fragment
    at a time. A "sentence" here ends at '.', '!', '?', or a newline.

    Any trailing partial sentence still buffered once ``chunks`` is
    exhausted is yielded as a final piece, so no text is ever dropped.

    Args:
        chunks: An iterable (typically a generator) of small text
            pieces, in order.

    Yields:
        Complete sentences, each stripped of leading/trailing
        whitespace, in the order they were completed.
    """
    buffer = ""

    for chunk in chunks:
        buffer += chunk

        while True:
            cut = _find_sentence_end(buffer)

            if cut is None:
                break

            sentence, buffer = buffer[:cut].strip(), buffer[cut:]

            if sentence:
                yield sentence

    remainder = buffer.strip()

    if remainder:
        yield remainder


def _find_sentence_end(buffer: str) -> int | None:
    """Returns the index just past the first sentence-ending
    character in ``buffer``, or ``None`` if it doesn't contain one."""
    for index, character in enumerate(buffer):
        if character in _SENTENCE_ENDERS:
            return index + 1

    return None


# Unicode range for the Devanagari script, used to write Hindi (among
# other languages). Presence of these characters is a strong,
# essentially unambiguous signal that a piece of text is Hindi —
# unlike romanized Hinglish ("notepad kholo"), which uses the same
# Latin letters as English and can't be reliably told apart from it by
# script alone.
_DEVANAGARI_RANGE = range(0x0900, 0x0980)

# A sentence needs at least this many Devanagari characters before
# being called Hindi-dominant, so a single stray word or transliterated
# proper noun doesn't flip an otherwise-English sentence's voice.
_MIN_DEVANAGARI_CHARS = 3


def detect_reply_language(text: str) -> str | None:
    """
    Guesses whether ``text`` is Hindi-dominant, by script rather than
    by anything EON was told about who's speaking.

    This matters for text-to-speech in particular: which voice EON
    replies with should match what the reply text actually *is*, not
    just what language the user's spoken input (if any) was detected
    as. Typed input never goes through speech recognition at all, so
    without this, a Hindi-language reply to *typed* Hinglish would
    always get spoken in the default English voice — mispronouncing
    Devanagari script with English phonemes, which is unintelligible
    rather than merely accented.

    Only recognizes Devanagari script, not romanized Hinglish — "kholo"
    written in Latin letters looks like English by script and can't be
    told apart from it this way. That's an inherent limit of a
    script-based check, not something a longer character range would
    fix.

    Args:
        text: The text to check — typically one sentence of a
            streamed reply.

    Returns:
        ``"hi"`` if ``text`` contains enough Devanagari characters to
        call it Hindi-dominant, otherwise ``None`` (meaning "no
        script-based signal either way — let the caller fall back to
        whatever it already had").
    """
    devanagari_count = sum(1 for ch in text if ord(ch) in _DEVANAGARI_RANGE)
    return "hi" if devanagari_count >= _MIN_DEVANAGARI_CHARS else None
