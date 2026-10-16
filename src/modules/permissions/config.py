"""
Permissions Configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from src.modules.actions.models import ActionType

# Action types EON may run immediately, with no confirmation.
#
# This is deliberately an ALLOW-list, not a block-list: anything NOT
# in this set — including any new ActionType added later and never
# added here — defaults to requiring confirmation. A new capability
# being risky-by-default until someone deliberately marks it safe is
# much better than the reverse (silently exposed the moment it's
# added, because nobody remembered to add it to a block-list).
#
# Kept in sync with the two examples from the original feature
# request: "open" and "search" actions here run immediately; "delete"-
# and "send"-style actions (RUN_COMMAND, ORGANIZE_FILES, TYPE_TEXT,
# CLIPBOARD_WRITE, WINDOW_CONTROL, CALENDAR_CREATE, EMAIL_SEND,
# MESSAGE_SEND, and anything unrecognized) are not in this list, so
# they ask first.
DEFAULT_AUTO_ACTION_TYPES: frozenset[ActionType] = frozenset(
    {
        ActionType.CHAT,
        ActionType.OPEN_APP,
        ActionType.SEARCH_WEB,
        ActionType.OPEN_URL,
        ActionType.VIEW_SCREEN,
        ActionType.CLIPBOARD_READ,
        ActionType.VOLUME_CONTROL,
        ActionType.BRIGHTNESS_CONTROL,
        ActionType.TAKE_SCREENSHOT,
        ActionType.CALENDAR_READ,
        ActionType.EMAIL_READ,
        # Playing a song is the same kind of act as VOLUME_CONTROL or
        # OPEN_URL, both already here: it makes a noise and possibly
        # opens a browser tab, and there's nothing to leak or destroy.
        # Leaving it out would mean a yes/no prompt before every
        # "play music", which is friction for no safety gain.
        ActionType.MUSIC,
    }
)


# Action types requiring EON's highest tier — VERIFY, not just
# CONFIRM. These are the ones a stranger in the room benefits from
# most if they can just say "yes": running an arbitrary command,
# deleting/moving files (bundled into ORGANIZE_FILES along with
# harmless renames — see file_organizer.py — but there's no separate
# "delete" ActionType to single out, so the whole bundle is treated as
# high-risk), and sending something external (email, chat message).
#
# Matches the three examples from the feature request verbatim:
# "delete, send, run arbitrary commands."
HIGH_RISK_ACTION_TYPES: frozenset[ActionType] = frozenset(
    {
        ActionType.RUN_COMMAND,
        ActionType.ORGANIZE_FILES,
        ActionType.EMAIL_SEND,
        ActionType.MESSAGE_SEND,
    }
)


@dataclass(slots=True)
class PermissionsServiceConfig:
    """
    Configuration for the permissions/confirmation layer.

    Attributes:
        enabled: Master switch. If ``False``, every action runs
            immediately regardless of its classification — the
            behavior EON had before this module existed.
        auto_action_types: Action types that may run without asking.
            Anything not in this set requires a yes/no first.
        high_risk_action_types: Action types requiring EON's highest
            tier (VERIFY) — the authorization passphrase, not just a
            yes/no. Checked before ``auto_action_types``, so listing a
            type in both would make VERIFY win, though in practice
            there's no reason to do that.
        authorization_passphrase: The phrase whoever's talking to EON
            must say/type to approve a VERIFY-tier action — e.g.
            "only Tony can authorize this". Loaded from the
            AUTHORIZATION_PASSPHRASE environment variable (see
            ``PermissionsServiceConfig.from_env``), never hardcoded or
            put in settings.json, for the same reason API keys live in
            ``.env`` elsewhere in EON: it's a secret, not a setting.
            ``None``/empty means no passphrase is configured — VERIFY
            actions then fall back to a plain yes/no, same as CONFIRM,
            and EON logs a warning at startup that high-risk actions
            aren't actually protected against "whoever's in the room."
        max_verify_attempts: How many wrong passphrase attempts are
            allowed before a VERIFY confirmation is denied outright,
            rather than left open to keep guessing.
        confirmation_timeout_seconds: How long a pending confirmation
            stays open. After this, it's treated as expired, and the
            next message is processed as a fresh request instead of
            being interpreted as a yes/no.
    """

    enabled: bool = True
    auto_action_types: frozenset[ActionType] = field(
        default_factory=lambda: DEFAULT_AUTO_ACTION_TYPES
    )
    high_risk_action_types: frozenset[ActionType] = field(
        default_factory=lambda: HIGH_RISK_ACTION_TYPES
    )
    authorization_passphrase: str | None = None
    max_verify_attempts: int = 3
    confirmation_timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls, **kwargs) -> "PermissionsServiceConfig":
        """
        Builds the config with ``authorization_passphrase`` read from
        the AUTHORIZATION_PASSPHRASE environment variable (via
        ``.env`` — see ``src/core/config.py``, which calls
        ``load_dotenv()`` at startup). Any other field can still be
        overridden via ``kwargs``, same as calling the constructor
        directly.
        """

        return cls(
            authorization_passphrase=os.getenv("AUTHORIZATION_PASSPHRASE") or None,
            **kwargs,
        )
