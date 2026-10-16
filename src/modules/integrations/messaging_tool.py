"""
Messaging Tool.

Sends a message via whichever provider is configured
(messaging_provider in config/settings.json): a Telegram bot, or a
Slack incoming webhook. Both were picked specifically because they
need no OAuth flow, unlike WhatsApp/iMessage/most other chat
platforms' APIs — just a bot token or a webhook URL, each obtainable
in a couple of minutes:

- Telegram: message @BotFather, "/newbot", copy the token it gives
  you into TELEGRAM_BOT_TOKEN in .env. Then message your new bot once
  (anything) so it can see your chat — EON can't message you first;
  Telegram doesn't allow bots to initiate a conversation. Get your
  chat ID from https://api.telegram.org/bot<TOKEN>/getUpdates and put
  it in TELEGRAM_CHAT_ID.
- Slack: in a workspace you can add apps to, create an "Incoming
  Webhook" and put the URL it gives you in SLACK_WEBHOOK_URL in .env.

This is deliberately a small, provider-agnostic tool rather than a
deep integration with either platform (no reading messages, no
threads/channels) — "have EON notify me somewhere" is the feature;
a full chat client is a different, much bigger project.
"""

from __future__ import annotations

import re

from src.core.logger import get_logger
from src.modules.integrations.config import IntegrationsConfig
from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

logger = get_logger("Integrations.Messaging")

# "to <recipient> saying/that says <message>" with the recipient part
# optional — if omitted, the configured default chat/webhook is used.
_SEND_PATTERN = re.compile(
    r"(?:to\s+(?P<to>\S+)\s+)?(?:saying|that says|with the message)\s+"
    r"(?P<body>.+)$",
    re.IGNORECASE,
)


class MessagingTool(Tool):
    """Tool to send a chat message via Telegram or Slack."""

    def __init__(
        self,
        config: IntegrationsConfig,
    ) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "messaging"

    def execute(self, text: str = "") -> ToolResult:
        if not self._config.messaging_enabled:
            return ToolResult(
                success=False,
                message=(
                    "Messaging is currently disabled, sir. Enable "
                    "'messaging_enabled' in config/settings.json to "
                    "turn it on."
                ),
            )

        match = _SEND_PATTERN.search(text.strip())
        body = match.group("body").strip() if match else text.strip()
        recipient = match.group("to") if match and match.group("to") else None

        if not body:
            return ToolResult(
                success=False,
                message=(
                    "I didn't catch what to send — try something like "
                    "'send a message saying I'm running 10 minutes late'."
                ),
            )

        provider = self._config.messaging_provider.lower()

        if provider == "telegram":
            return self._send_telegram(body, recipient)

        if provider == "slack":
            return self._send_slack(body)

        return ToolResult(
            success=False,
            message=(
                f"Unknown messaging provider '{provider}'. Set "
                f"'messaging_provider' in config/settings.json to "
                f"'telegram' or 'slack'."
            ),
        )

    def _send_telegram(self, body: str, recipient: str | None) -> ToolResult:
        token = self._config.telegram_bot_token
        chat_id = recipient or self._config.telegram_chat_id

        if not token or not chat_id:
            return ToolResult(
                success=False,
                message=(
                    "Telegram isn't configured — set TELEGRAM_BOT_TOKEN "
                    "and TELEGRAM_CHAT_ID in .env. See "
                    "src/modules/integrations/messaging_tool.py for "
                    "setup steps."
                ),
            )

        try:
            import httpx

            response = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": body},
                timeout=10.0,
            )
            response.raise_for_status()
        except Exception as error:
            logger.exception("Telegram sendMessage failed.")
            return ToolResult(
                success=False,
                message=f"I couldn't send that via Telegram: {error}",
            )

        return ToolResult(success=True, message="Message sent via Telegram.")

    def _send_slack(self, body: str) -> ToolResult:
        webhook_url = self._config.slack_webhook_url

        if not webhook_url:
            return ToolResult(
                success=False,
                message=(
                    "Slack isn't configured — set SLACK_WEBHOOK_URL in "
                    ".env. See src/modules/integrations/messaging_tool.py "
                    "for setup steps."
                ),
            )

        try:
            import httpx

            response = httpx.post(
                webhook_url,
                json={"text": body},
                timeout=10.0,
            )
            response.raise_for_status()
        except Exception as error:
            logger.exception("Slack webhook post failed.")
            return ToolResult(
                success=False,
                message=f"I couldn't send that via Slack: {error}",
            )

        return ToolResult(success=True, message="Message sent via Slack.")
