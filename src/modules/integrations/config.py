"""
Integrations Configuration.

Calendar/email need a Google OAuth client secret; messaging needs a
bot token or webhook URL. None of that belongs in config/settings.json
(which is plain JSON, versioned, and not a secrets store) — it's read
from environment variables instead, loaded from a local `.env` file
via python-dotenv (see ``src/core/config.py``, which calls
``load_dotenv()`` once at startup).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class IntegrationsConfig:
    """
    Configuration for the Calendar/Email/Messaging integrations.

    Attributes:
        calendar_enabled: Master switch for calendar reads/creates.
        email_enabled: Master switch for email reads/sends.
        messaging_enabled: Master switch for sending chat messages.
        messaging_provider: Which messaging backend to use —
            ``"telegram"`` or ``"slack"``.
        google_credentials_path: Path to the OAuth client secret JSON
            downloaded from Google Cloud Console (Calendar + Gmail
            share one, since they use the same Google account/consent
            flow). Defaults to ``config/google_credentials.json``.
        google_token_path: Where the cached user token is stored after
            the first interactive consent, so EON doesn't re-open a
            browser every time. Defaults to
            ``data/google_token.json``.
        telegram_bot_token: Bot token from @BotFather (Telegram
            provider only).
        telegram_chat_id: Default chat/user ID to send messages to
            (Telegram provider only).
        slack_webhook_url: Incoming webhook URL (Slack provider only).
    """

    calendar_enabled: bool = True
    email_enabled: bool = True
    messaging_enabled: bool = True
    messaging_provider: str = "telegram"

    google_credentials_path: str = "config/google_credentials.json"
    google_token_path: str = "data/google_token.json"

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    slack_webhook_url: str | None = None

    @classmethod
    def from_env(
        cls,
        calendar_enabled: bool = True,
        email_enabled: bool = True,
        messaging_enabled: bool = True,
        messaging_provider: str = "telegram",
    ) -> "IntegrationsConfig":
        """
        Builds the config from environment variables, with the
        enabled flags/provider choice passed in from
        config/settings.json (the same split used elsewhere in EON:
        on/off + which-provider in settings.json, secrets in `.env`).
        """

        return cls(
            calendar_enabled=calendar_enabled,
            email_enabled=email_enabled,
            messaging_enabled=messaging_enabled,
            messaging_provider=messaging_provider,
            google_credentials_path=os.getenv(
                "GOOGLE_CREDENTIALS_PATH", "config/google_credentials.json"
            ),
            google_token_path=os.getenv(
                "GOOGLE_TOKEN_PATH", "data/google_token.json"
            ),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
        )
