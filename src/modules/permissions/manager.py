"""
Permission Manager.

Gates plans containing risky action types behind an explicit yes/no
from the user before EON executes them. This sits on top of, not
instead of, Reasoning's hard safety blocklist: Reasoning refuses
outright destructive commands unconditionally; PermissionManager asks
first for things that are allowed but deserve a nod (deleting files,
running arbitrary commands, sending/typing text, etc.).
"""

from __future__ import annotations

import re
import string
from datetime import datetime, timedelta
from uuid import uuid4

from src.core.logger import get_logger
from src.modules.actions.models import ActionType
from src.modules.permissions.config import PermissionsServiceConfig
from src.modules.permissions.models import (
    ConfirmationOutcome,
    PendingConfirmation,
    PermissionLevel,
)
from src.modules.planner.models import Plan

logger = get_logger("Permissions")

_AFFIRMATIVE_WORDS = (
    "yes", "yeah", "yep", "yup", "confirm", "confirmed",
    "go ahead", "sure", "ok", "okay", "proceed", "do it",
)
_NEGATIVE_WORDS = (
    "no", "nope", "nah", "cancel", "don't", "dont",
    "stop", "never mind", "nevermind", "abort",
)

_ACTION_DESCRIPTIONS: dict[ActionType, str] = {
    ActionType.RUN_COMMAND: "run the command: {target}",
    ActionType.ORGANIZE_FILES: "organize files: {target}",
    ActionType.CLIPBOARD_WRITE: "overwrite the clipboard with: {target}",
    ActionType.TYPE_TEXT: "type this into the focused app: {target}",
    ActionType.WINDOW_CONTROL: "change a window's state: {target}",
    ActionType.CALENDAR_CREATE: "add this to your calendar: {target}",
    ActionType.EMAIL_SEND: "send this email: {target}",
    ActionType.MESSAGE_SEND: "send this message: {target}",
}

# Strips punctuation and collapses whitespace/case before comparing a
# spoken/typed passphrase attempt to the configured one — an exact
# string match would fail on trivial, meaningless differences (a
# trailing period from punctuation-aware STT, extra spaces, "Only
# Tony" vs "only tony"). Still an exact match otherwise, deliberately:
# fuzzy/approximate matching would make the passphrase guessable by
# degrees, which defeats the point of it.
_PUNCTUATION_TABLE = str.maketrans("", "", string.punctuation)


def _normalize_phrase(text: str) -> str:
    return " ".join(text.translate(_PUNCTUATION_TABLE).lower().split())


class PermissionManager:
    """
    Classifies plans as safe-to-run or needing confirmation, and
    tracks the single pending confirmation (if any) while EON waits
    for the user's answer.

    Only one confirmation can be pending at a time, matching EON's
    current single-session console/wake-word loop. A second request
    arriving while one is already pending simply replaces it — asking
    about two different risky actions at once would be more confusing
    than useful here.
    """

    def __init__(self, config: PermissionsServiceConfig) -> None:
        self._config = config
        self._pending: PendingConfirmation | None = None

    @property
    def passphrase_configured(self) -> bool:
        """Whether an authorization passphrase is set up — used by
        callers building user-facing confirmation prompts, so they
        don't need to reach into the private config themselves."""
        return bool(self._config.authorization_passphrase)

    def classify(self, plan: Plan) -> PermissionLevel:
        """
        Returns VERIFY if any step is a high-risk action type (needs
        the authorization passphrase, not just a yes/no), CONFIRM if
        any step isn't in the auto-approve allow-list, AUTO if every
        step is.
        """
        if not self._config.enabled:
            return PermissionLevel.AUTO

        if any(
            step.action.type in self._config.high_risk_action_types
            for step in plan.steps
        ):
            return PermissionLevel.VERIFY

        for step in plan.steps:
            if step.action.type not in self._config.auto_action_types:
                return PermissionLevel.CONFIRM

        return PermissionLevel.AUTO

    def has_pending(self) -> bool:
        """
        Whether a confirmation is currently on record, expired or not.

        Deliberately does *not* clear an expired confirmation itself —
        that transition belongs to ``resolve``, so a caller that checks
        ``has_pending()`` and then calls ``resolve()`` reliably gets an
        ``EXPIRED`` outcome back instead of the state having already
        been silently cleared out from under it.
        """
        return self._pending is not None

    def request(self, plan: Plan) -> PendingConfirmation:
        """
        Records ``plan`` as awaiting confirmation and returns it.

        Replaces any previous pending confirmation.
        """
        now = datetime.now()
        level = self.classify(plan)

        pending = PendingConfirmation(
            id=uuid4(),
            plan=plan,
            description=self._describe(plan),
            level=level,
            created_at=now,
            expires_at=now + timedelta(seconds=self._config.confirmation_timeout_seconds),
        )

        self._pending = pending

        logger.info("Requested confirmation %s: %s", pending.id, pending.description)

        return pending

    def resolve(self, user_message: str) -> tuple[ConfirmationOutcome, PendingConfirmation | None]:
        """
        Checks ``user_message`` against the pending confirmation, if
        any.

        Returns:
            A ``(outcome, pending)`` pair. ``pending`` is the
            confirmation that was resolved (for CONFIRMED/DENIED/
            EXPIRED) or the one still waiting (for NOT_A_RESPONSE), or
            ``None`` if nothing was pending to begin with.
        """
        if self._pending is None:
            return ConfirmationOutcome.NOT_A_RESPONSE, None

        if datetime.now() >= self._pending.expires_at:
            expired = self._pending
            self._pending = None
            logger.info("Pending confirmation %s expired.", expired.id)
            return ConfirmationOutcome.EXPIRED, expired

        text = user_message.strip().lower()

        # A negative word declines either tier — cancelling doesn't
        # need the passphrase, only approving a VERIFY-tier action
        # does.
        if self._matches_any(text, _NEGATIVE_WORDS):
            denied = self._pending
            self._pending = None
            logger.info("Confirmation %s denied.", denied.id)
            return ConfirmationOutcome.DENIED, denied

        if self._pending.level == PermissionLevel.VERIFY:
            return self._resolve_verify(user_message)

        if self._matches_any(text, _AFFIRMATIVE_WORDS):
            confirmed = self._pending
            self._pending = None
            logger.info("Confirmation %s confirmed.", confirmed.id)
            return ConfirmationOutcome.CONFIRMED, confirmed

        return ConfirmationOutcome.NOT_A_RESPONSE, self._pending

    def _resolve_verify(
        self, user_message: str
    ) -> tuple[ConfirmationOutcome, PendingConfirmation | None]:
        """
        Checks a passphrase attempt against a VERIFY-tier pending
        confirmation. Unlike CONFIRM, a plain "yes" does nothing here —
        only matching the configured authorization passphrase approves
        it. This is the actual "only Tony can authorize this" check:
        anyone can say yes, only whoever knows the passphrase can
        approve a high-risk action.
        """
        pending = self._pending

        if not self._config.authorization_passphrase:
            # No passphrase configured at all — VERIFY degrades to a
            # plain yes/no, same as CONFIRM. Already warned loudly
            # about this at startup (see bootstrap/services.py); this
            # per-confirmation warning is the reminder that this
            # specific approval wasn't actually identity-checked.
            if self._matches_any(user_message.strip().lower(), _AFFIRMATIVE_WORDS):
                self._pending = None
                logger.warning(
                    "Confirmation %s (high-risk, NO passphrase "
                    "configured) approved with a plain yes/no.",
                    pending.id,
                )
                return ConfirmationOutcome.CONFIRMED, pending
            return ConfirmationOutcome.NOT_A_RESPONSE, pending

        if _normalize_phrase(user_message) == _normalize_phrase(
            self._config.authorization_passphrase
        ):
            self._pending = None
            logger.info("Confirmation %s verified via passphrase.", pending.id)
            return ConfirmationOutcome.CONFIRMED, pending

        pending.verify_attempts += 1
        logger.warning(
            "Confirmation %s: wrong passphrase (attempt %d/%d).",
            pending.id,
            pending.verify_attempts,
            self._config.max_verify_attempts,
        )

        if pending.verify_attempts >= self._config.max_verify_attempts:
            self._pending = None
            logger.warning(
                "Confirmation %s denied after too many wrong "
                "passphrase attempts.",
                pending.id,
            )
            return ConfirmationOutcome.DENIED, pending

        return ConfirmationOutcome.NOT_A_RESPONSE, pending

    def discard(self) -> PendingConfirmation | None:
        """Drops the pending confirmation, if there is one.

        Distinct from resolving it with "no": nothing was declined
        here, the user simply moved on to something else. Kept
        separate so the log says what actually happened.

        Returns:
            The confirmation that was dropped, or ``None`` if there
            was nothing pending.
        """
        dropped = self._pending
        self._pending = None

        if dropped is not None:
            logger.info(
                "Pending confirmation %s dropped (the user moved on).",
                dropped.id,
            )

        return dropped

    def describe_pending(self) -> str | None:
        """A reminder message for when a reply didn't look like a
        valid response, so the user knows what EON is still waiting
        on."""
        if self._pending is None:
            return None

        if self._pending.level == PermissionLevel.VERIFY and self._config.authorization_passphrase:
            return (
                f"You still have a high-risk action waiting: "
                f"{self._pending.description}. Say the authorization "
                "passphrase to proceed, or 'cancel' to back out."
            )

        return (
            f"You still have a pending action: {self._pending.description}. "
            "Say 'yes' to proceed, or 'no' to cancel."
        )

    @staticmethod
    def _matches_any(text: str, words: tuple[str, ...]) -> bool:
        for word in words:
            if re.search(rf"\b{re.escape(word)}\b", text):
                return True
        return False

    @staticmethod
    def _describe(plan: Plan) -> str:
        parts = []

        for step in plan.steps:
            action = step.action
            template = _ACTION_DESCRIPTIONS.get(action.type)
            target = action.target or "(no target given)"

            if template:
                parts.append(template.format(target=target))
            else:
                parts.append(f"{action.type.value}: {target}")

        return "; ".join(parts) if parts else plan.goal.description
