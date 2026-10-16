"""Tests for stripping markdown out of text before it is spoken.

A console reader's eye skips `**` and backticks; a TTS voice says them
out loud. These cases are taken from real EON replies — the model emits
markdown headings whether or not anyone asked for them.

Pure logic, no audio involved.
"""

from __future__ import annotations

from src.utils.text import to_speech_text


def test_plain_text_is_untouched():
    text = "Certainly, sir. Japan is an island country in East Asia."

    assert to_speech_text(text) == text


def test_a_bold_heading_loses_its_markers():
    # Exactly the shape that had EON saying "asterisk asterisk Japan
    # colon asterisk asterisk".
    assert to_speech_text("**Japan:**") == "Japan,"


def test_a_bold_heading_followed_by_a_sentence():
    cleaned = to_speech_text(
        "**Japan:**\nJapan is an island nation in East Asia."
    )

    assert cleaned == "Japan, Japan is an island nation in East Asia."


def test_the_real_headline_from_the_log():
    cleaned = to_speech_text("**First headline:**")

    assert cleaned == "First headline,"
    assert "*" not in cleaned
    assert ":" not in cleaned


def test_a_plain_trailing_colon_becomes_a_pause():
    assert (
        to_speech_text("Here's something about Japan:")
        == "Here's something about Japan,"
    )


def test_a_colon_inside_a_list_of_items():
    cleaned = to_speech_text(
        "It consists of four main islands: Honshu, Hokkaido, Kyushu."
    )

    assert cleaned == (
        "It consists of four main islands, Honshu, Hokkaido, Kyushu."
    )


def test_a_time_keeps_its_colon():
    # "12,30" would be a real regression, not a cosmetic one.
    assert to_speech_text("The alarm is set for 12:30.") == (
        "The alarm is set for 12:30."
    )


def test_bullets_lose_their_markers():
    assert to_speech_text("- sushi\n- ramen") == "sushi ramen"


def test_asterisk_bullets_lose_their_markers():
    assert to_speech_text("* sushi\n* ramen") == "sushi ramen"


def test_numbered_list_markers_are_dropped():
    assert to_speech_text("1. sushi\n2. ramen") == "sushi ramen"


def test_a_hash_heading_loses_its_markers():
    assert to_speech_text("## Summary\nAll good.") == "Summary All good."


def test_bold_and_italic_are_unwrapped():
    assert to_speech_text("**bold** and *italic* here") == (
        "bold and italic here"
    )


def test_underscore_emphasis_is_unwrapped():
    assert to_speech_text("__bold__ and _italic_") == "bold and italic"


def test_inline_code_loses_its_backticks():
    assert to_speech_text("Saved to `data/lists.json` now.") == (
        "Saved to data/lists.json now."
    )


def test_a_code_fence_is_removed_entirely():
    assert to_speech_text("Try this:\n```python\nprint(1)\n```\nDone.") == (
        "Try this, Done."
    )


def test_a_markdown_link_keeps_its_label_only():
    assert to_speech_text("See [the docs](https://example.com) for more.") == (
        "See the docs for more."
    )


def test_a_stray_asterisk_is_dropped():
    # Unpaired asterisks survive the paired patterns, and a voice would
    # still read them out.
    cleaned = to_speech_text("That is *really* good * stuff.")

    assert "*" not in cleaned
    assert "really" in cleaned


def test_whitespace_is_collapsed():
    assert to_speech_text("one\n\n\n   two") == "one two"


def test_snake_case_identifiers_survive():
    # Underscores between word characters are not emphasis.
    assert to_speech_text("the file is called lists_path ok") == (
        "the file is called lists_path ok"
    )
