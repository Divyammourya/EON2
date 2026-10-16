"""
Proactive Speech Models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class Reminder:
    """
    A one-off spoken reminder scheduled for a specific time.

    Attributes:
        id: Unique identifier, returned by ``ProactiveService.remind_at``
            so the caller can cancel it later if needed.
        message: The exact text EON will speak when this fires.
        due_at: The point in time this reminder becomes due. Any tick
            at or after this time fires it (there's no hard deadline
            after which it's dropped).
        spoken: Whether this reminder has already been spoken. Fired
            reminders are removed from ``ProactiveService`` right
            after speaking, so in practice this is always ``False``
            for anything still tracked — kept as a field mainly to
            make a single tick's logic easy to reason about and test.
    """

    message: str
    due_at: datetime
    id: UUID = field(default_factory=uuid4)
    spoken: bool = False
