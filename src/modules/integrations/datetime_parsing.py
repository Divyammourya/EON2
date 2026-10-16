"""
Lightweight relative date/time parsing for calendar event creation.

Deliberately not a general natural-language date parser (no new
dependency like `dateparser`) — just the handful of patterns people
actually use when telling an assistant to schedule something:
"today"/"tomorrow"/"next <weekday>"/a bare weekday name, plus a time of
day ("3pm", "10:30am", "noon", "midnight"). Anything fancier falls back
to sensible defaults rather than guessing wildly.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_TIME_PATTERN = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE
)

_DEFAULT_DURATION = timedelta(hours=1)
_DEFAULT_HOUR = 9  # used when no time of day is mentioned at all


def parse_when(
    text: str,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """
    Best-effort parse of a date/time reference out of natural
    language.

    Returns a ``(start, end)`` pair, defaulting to a 1-hour event.
    Never raises — anything it can't confidently parse falls back to
    "tomorrow at 9am" rather than guessing at something more specific
    and likely wrong.
    """

    now = now or datetime.now()
    text = text.lower()

    day = _resolve_day(text, now)
    hour, minute = _resolve_time(text)

    start = day.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # If no date was mentioned at all, "3pm" alone should mean the
    # next 3pm — today if that's still ahead, otherwise tomorrow.
    if start <= now and not _mentions_a_day(text):
        start += timedelta(days=1)

    return start, start + _DEFAULT_DURATION


def _resolve_day(text: str, now: datetime) -> datetime:
    if "tomorrow" in text:
        return now + timedelta(days=1)

    if "today" in text or "tonight" in text:
        return now

    for name, index in _WEEKDAYS.items():
        if name not in text:
            continue

        days_ahead = (index - now.weekday()) % 7

        # "next <weekday>" always means the following week's
        # occurrence, even if that weekday hasn't happened yet this
        # week; a bare weekday name means the closest upcoming one.
        if "next " + name in text or days_ahead == 0:
            days_ahead = days_ahead or 7
        return now + timedelta(days=days_ahead)

    return now


def _resolve_time(text: str) -> tuple[int, int]:
    if "noon" in text:
        return 12, 0

    if "midnight" in text:
        return 0, 0

    match = _TIME_PATTERN.search(text)

    if not match:
        return _DEFAULT_HOUR, 0

    hour = int(match.group(1)) % 12
    minute = int(match.group(2) or 0)

    if match.group(3).lower() == "pm":
        hour += 12

    return hour, minute


def _mentions_a_day(text: str) -> bool:
    return (
        "tomorrow" in text
        or "today" in text
        or "tonight" in text
        or any(name in text for name in _WEEKDAYS)
    )
