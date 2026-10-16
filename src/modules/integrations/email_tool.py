"""
Email Tool.

Reads recent/unread Gmail messages, or sends a new one, via the Gmail
API. Shares Google OAuth with the Calendar tool (see google_auth.py).
"""

from __future__ import annotations

import base64
import re
from email.mime.text import MIMEText

from src.core.logger import get_logger
from src.modules.integrations.google_auth import GoogleAuthError, GoogleAuthManager
from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

logger = get_logger("Integrations.Email")

_MAX_MESSAGES_LISTED = 5
_MAX_SNIPPET_CHARS = 120

# "to <email> saying/about/that says <body>", optionally with
# "subject <subject>" before the body. Deliberately simple pattern
# matching, same spirit as the rest of EON's rule-based parsing —
# see intent/classifier.py.
_SEND_PATTERN = re.compile(
    r"to\s+(?P<to>[\w.+-]+@[\w-]+\.[\w.-]+)"
    r"(?:\s+subject\s+(?P<subject>.+?))?"
    r"\s+(?:saying|about|that says|with the message)\s+(?P<body>.+)$",
    re.IGNORECASE,
)


class EmailTool(Tool):
    """Tool to read recent Gmail messages, or send a new one."""

    def __init__(
        self,
        enabled: bool = True,
        auth: GoogleAuthManager | None = None,
    ) -> None:
        self.enabled = enabled
        self._auth = auth

    @property
    def name(self) -> str:
        return "email"

    def execute(self, text: str = "") -> ToolResult:
        """
        Args:
            text: Prefixed with ``"read:"`` or ``"send:"`` by the
                action executor — reading is auto-approved, sending
                requires confirmation (see permissions/config.py).
        """

        if not self.enabled:
            return ToolResult(
                success=False,
                message=(
                    "Email access is currently disabled, sir. Enable "
                    "'email_enabled' in config/settings.json to turn "
                    "it on."
                ),
            )

        if text.startswith("send:"):
            return self._send(text[len("send:") :].strip())

        query = text[len("read:") :].strip() if text.startswith("read:") else text.strip()

        return self._read(query)

    def _service(self):
        if self._auth is None:
            raise GoogleAuthError(
                "Email isn't configured — no Google auth manager was "
                "wired in."
            )

        from googleapiclient.discovery import build

        creds = self._auth.get_credentials()

        return build("gmail", "v1", credentials=creds)

    def _read(self, query: str) -> ToolResult:
        try:
            service = self._service()
        except GoogleAuthError as error:
            return ToolResult(success=False, message=str(error))
        except Exception as error:
            logger.exception("Failed to build the Gmail service.")
            return ToolResult(success=False, message=str(error))

        gmail_query = "is:unread" if "unread" not in query else query
        if not query:
            gmail_query = "is:unread"

        try:
            response = (
                service.users()
                .messages()
                .list(userId="me", q=gmail_query, maxResults=_MAX_MESSAGES_LISTED)
                .execute()
            )
        except Exception as error:
            logger.exception("Gmail messages.list failed.")
            return ToolResult(
                success=False,
                message=f"I couldn't reach your inbox: {error}",
            )

        message_refs = response.get("messages", [])

        if not message_refs:
            return ToolResult(
                success=True,
                message="Nothing new in your inbox, sir.",
            )

        lines = []

        for ref in message_refs:
            try:
                full = (
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=ref["id"],
                        format="metadata",
                        metadataHeaders=["From", "Subject"],
                    )
                    .execute()
                )
            except Exception:
                logger.exception("Gmail messages.get failed for %s", ref["id"])
                continue

            lines.append(self._format_message(full))

        return ToolResult(success=True, message="\n".join(lines))

    def _send(self, details: str) -> ToolResult:
        match = _SEND_PATTERN.search(details)

        if not match:
            return ToolResult(
                success=False,
                message=(
                    "I didn't catch that — try something like 'send an "
                    "email to jane@example.com saying the report is "
                    "ready'."
                ),
            )

        try:
            service = self._service()
        except GoogleAuthError as error:
            return ToolResult(success=False, message=str(error))
        except Exception as error:
            logger.exception("Failed to build the Gmail service.")
            return ToolResult(success=False, message=str(error))

        to_address = match.group("to")
        subject = (match.group("subject") or "").strip() or "(no subject)"
        body = match.group("body").strip()

        message = MIMEText(body)
        message["to"] = to_address
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        try:
            service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
        except Exception as error:
            logger.exception("Gmail messages.send failed.")
            return ToolResult(
                success=False,
                message=f"I couldn't send that email: {error}",
            )

        return ToolResult(
            success=True,
            message=f"Email sent to {to_address}.",
        )

    @staticmethod
    def _format_message(message: dict) -> str:
        headers = {
            h["name"]: h["value"]
            for h in message.get("payload", {}).get("headers", [])
        }

        sender = headers.get("From", "unknown sender")
        subject = headers.get("Subject", "(no subject)")
        snippet = message.get("snippet", "")

        if len(snippet) > _MAX_SNIPPET_CHARS:
            snippet = snippet[:_MAX_SNIPPET_CHARS] + "..."

        return f"- From {sender} — {subject}: {snippet}"
