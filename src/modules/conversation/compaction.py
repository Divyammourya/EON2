"""Conversation compaction: keeping long sessions inside the context window.

Why this exists
---------------
Every turn is sent to the model along with the whole conversation so far.
A long session eventually outgrows the model's context window, and the
oldest turns get dropped — silently. EON then "forgets" what it was doing
ten minutes ago, and the user has to repeat themselves.

This module folds the *older* part of a conversation into a short summary
that is carried forward in the system prompt, while the most recent turns
are kept verbatim. A long session stays coherent without the history
growing without bound.

What's here is pure decision/formatting logic, unit tested. The one LLM
call that actually writes the summary is made by ``Brain`` — see
``Brain._compact_history``.

Requires: Python 3.12+
"""

from __future__ import annotations

from src.modules.conversation.message import Message

SUMMARY_INSTRUCTION = (
    "You are compressing the earlier part of a conversation so it can be "
    "carried forward in a few lines.\n\n"
    "Summarise the exchange below in at most 150 words. Keep: names, "
    "decisions, facts about the user, anything still unresolved, and what "
    "was being worked on. Drop greetings, repetition and small talk.\n\n"
    "Write plain notes, not prose addressed to anyone. Do not add "
    "commentary, and do not invent anything that was not said."
)


def needs_compaction(message_count: int, max_messages: int) -> bool:
    """Whether the history has grown past the point where it should be folded."""
    return message_count > max_messages


def split_for_compaction(
    messages: list[Message],
    keep_last: int,
) -> tuple[list[Message], list[Message]]:
    """Splits history into ``(older, recent)``.

    The most recent ``keep_last`` messages are returned verbatim — they
    are what the model needs in full — and everything before them is what
    gets summarised.

    Args:
        messages: The conversation, oldest first.
        keep_last: How many trailing messages to keep unsummarised.

    Returns:
        ``(older, recent)``. ``older`` is empty when the history is
        already short enough to keep whole.
    """
    if keep_last <= 0:
        # Guard against ``messages[:-0]``, which is ``[]``, not the whole
        # list — the classic slice trap.
        return list(messages), []
    return messages[:-keep_last], messages[-keep_last:]


def build_compaction_messages(
    older: list[Message],
    previous_summary: str = "",
) -> list[dict]:
    """Builds the LLM messages that ask for a summary of ``older``.

    Args:
        older: The messages to fold away.
        previous_summary: A summary from an earlier compaction, if any.
            Included so successive summaries build on each other rather
            than losing everything folded away before.

    Returns:
        ``messages`` in the shape the AI manager expects.
    """
    transcript = "\n".join(
        f"{message.role}: {message.content}" for message in older
    )

    user_content = ""

    if previous_summary:
        user_content += (
            "Summary of the conversation so far:\n"
            f"{previous_summary}\n\n"
        )

    user_content += f"Newer exchanges to fold in:\n{transcript}"

    return [
        {"role": "system", "content": SUMMARY_INSTRUCTION},
        {"role": "user", "content": user_content},
    ]
