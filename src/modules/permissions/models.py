"""
Permission models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from src.modules.planner.models import Plan


class PermissionLevel(str, Enum):
    """How EON should treat a plan before executing it."""

    AUTO = "auto"
    """Execute immediately, no confirmation needed."""

    CONFIRM = "confirm"
    """Ask the user first and wait for a yes/no before executing."""

    VERIFY = "verify"
    """
    EON's highest tier, for actions that are hard or impossible to
    undo once another party is involved or a command runs (deleting
    files, sending an email/message, running an arbitrary command). A
    plain "yes" isn't enough here — whoever's talking to EON has to
    also give the configured authorization passphrase. This is what
    stops "someone else in the room just tells it to do things": a
    yes/no only confirms *that* something should happen, not *who* is
    asking for it.
    """


class ConfirmationOutcome(str, Enum):
    """Result of checking a user's reply against a pending confirmation."""

    CONFIRMED = "confirmed"
    DENIED = "denied"
    EXPIRED = "expired"
    NOT_A_RESPONSE = "not_a_response"


@dataclass(slots=True)
class PendingConfirmation:
    """
    A plan that's on hold, waiting for the user to say yes or no (or,
    for high-risk actions, give the authorization passphrase) before
    EON executes it.

    Attributes:
        id: Unique identifier for this confirmation request.
        plan: The plan that will run if confirmed.
        description: A short, human-readable summary of what the plan
            will do, shown to the user when asking for confirmation.
        level: Which tier this confirmation is — ``CONFIRM`` (yes/no)
            or ``VERIFY`` (needs the authorization passphrase, not
            just a yes/no). Determines how ``PermissionManager.resolve``
            checks the user's reply.
        created_at: When this confirmation was requested.
        expires_at: When this confirmation stops being valid. After
            this, a "yes"/passphrase no longer executes it — the next
            message is treated as a brand-new request instead.
        verify_attempts: How many times the passphrase has been
            entered wrong so far. Only relevant for ``level ==
            VERIFY`` — after enough wrong attempts, the confirmation is
            denied outright rather than left open indefinitely for
            guessing.
    """

    id: UUID
    plan: Plan
    description: str
    level: PermissionLevel
    created_at: datetime
    expires_at: datetime
    verify_attempts: int = 0
