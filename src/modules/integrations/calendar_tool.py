"""
Calendar Tool.

Reads and creates events on the user's primary Google Calendar via the
Google Calendar API. Requires a one-time OAuth consent handled by
``GoogleAuthManager`` — see google_auth.py for setup.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from src.core.logger import get_logger
from src.modules.integrations.datetime_parsing import parse_when
from src.modules.integrations.google_auth import GoogleAuthError, GoogleAuthManager
from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

logger = get_logger("Integrations.Calendar")

_MAX_EVENTS_LISTED = 10

# Only the leading verb+article is stripped here, not the whole
# CALENDAR_CREATE_TRIGGERS phrase — "schedule a meeting with the
# team" should end up titled "meeting with the team", not "with the
# team" (which is what stripping the full trigger, including the
# word "meeting" itself, would leave).
_LEADING_VERB_PATTERN = re.compile(
    r"^(?:schedule|add|create|book|put)\s+(?:an?\s+)?", re.IGNORECASE
)

# "<title> ... at <time>/on <day>" — split off whatever comes before
# the first time/date signal as the event title. Deliberately simple;
# see datetime_parsing.py for why a full NLP parser isn't used here.
_TITLE_SPLIT_PATTERN = re.compile(
    r"^(.*?)\s+(?:at|on|tomorrow|today|tonight|next\s+\w+|monday|tuesday|"
    r"wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)


class CalendarTool(Tool):
    """Tool to read upcoming events from, or add events to, the user's
    Google Calendar."""

    def __init__(
        self,
        enabled: bool = True,
        auth: GoogleAuthManager | None = None,
    ) -> None:
        self.enabled = enabled
        self._auth = auth

    @property
    def name(self) -> str:
        return "calendar"

    def execute(self, text: str = "") -> ToolResult:
        """
        Args:
            text: Prefixed with ``"read:"`` or ``"create:"`` by the
                action executor so this tool knows which operation was
                requested (reading is auto-approved, creating requires
                confirmation — see permissions/config.py — so the two
                need to stay distinguishable at the executor level).
        """

        if not self.enabled:
            return ToolResult(
                success=False,
                message=(
                    "Calendar access is currently disabled, sir. Enable "
                    "'calendar_enabled' in config/settings.json to turn "
                    "it on."
                ),
            )

        if text.startswith("create:"):
            return self._create_event(text[len("create:") :].strip())

        query = text[len("read:") :].strip() if text.startswith("read:") else text.strip()

        return self._read_events(query)

    def can_read_silently(self) -> bool:
        """Return whether background calendar reads should avoid OAuth prompts."""

        if not self.enabled or self._auth is None:
            return False

        checker = getattr(self._auth, "has_cached_credentials", None)

        if checker is None:
            return False

        return bool(checker())

    def _service(self):
        if self._auth is None:
            raise GoogleAuthError(
                "Calendar isn't configured — no Google auth manager "
                "was wired in."
            )

        from googleapiclient.discovery import build

        creds = self._auth.get_credentials()

        return build("calendar", "v3", credentials=creds)

    def _read_events(self, query: str) -> ToolResult:
        time_min, time_max = self._resolve_range(query)

        try:
            events = self.list_events_between(time_min, time_max)
        except GoogleAuthError as error:
            return ToolResult(success=False, message=str(error))
        except Exception as error:
            logger.exception("Failed to read calendar events.")
            return ToolResult(
                success=False,
                message=f"I couldn't reach your calendar: {error}",
            )

        if not events:
            return ToolResult(
                success=True,
                message="Nothing on your calendar for that period, sir.",
            )

        lines = [self._format_event(event) for event in events]

        return ToolResult(success=True, message="\n".join(lines))

    def list_events_between(
        self,
        start: datetime,
        end: datetime,
        max_results: int = _MAX_EVENTS_LISTED,
    ) -> list[dict]:
        """
        Return upcoming calendar events in a time range.
        """

        if not self.enabled:
            return []

        service = self._service()

        response = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start.isoformat() + "Z",
                timeMax=end.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime",
                maxResults=max_results,
            )
            .execute()
        )

        events = response.get("items", [])

        for event in events:
            event["start_at"] = self._parse_event_start(event)

        return events

    def _create_event(self, details: str) -> ToolResult:
        if not details:
            return ToolResult(
                success=False,
                message=(
                    "I didn't catch the event details — try something "
                    "like 'team sync tomorrow at 3pm'."
                ),
            )

        try:
            service = self._service()
        except GoogleAuthError as error:
            return ToolResult(success=False, message=str(error))
        except Exception as error:
            logger.exception("Failed to build the Calendar service.")
            return ToolResult(success=False, message=str(error))

        title = self._extract_title(details)
        start, end = parse_when(details)

        body = {
            "summary": title,
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        }

        try:
            created = (
                service.events()
                .insert(calendarId="primary", body=body)
                .execute()
            )
        except Exception as error:
            logger.exception("Calendar events.insert failed.")
            return ToolResult(
                success=False,
                message=f"I couldn't create that event: {error}",
            )

        link = created.get("htmlLink", "")

        return ToolResult(
            success=True,
            message=(
                f"Added '{title}' to your calendar for "
                f"{start.strftime('%A, %b %d at %-I:%M %p')}."
                + (f" {link}" if link else "")
            ),
        )

    @staticmethod
    def _resolve_range(query: str) -> tuple[datetime, datetime]:
        now = datetime.now()
        query = query.lower()

        if "tomorrow" in query:
            start = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return start, start + timedelta(days=1)

        if "week" in query:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, start + timedelta(days=7)

        # Default ("today" or no recognizable period): the rest of today.
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    @staticmethod
    def _extract_title(details: str) -> str:
        remainder = _LEADING_VERB_PATTERN.sub("", details, count=1)

        match = _TITLE_SPLIT_PATTERN.match(remainder)

        if match and match.group(1).strip():
            return match.group(1).strip()

        return remainder.strip() or details

    @staticmethod
    def _format_event(event: dict) -> str:
        summary = event.get("summary", "(no title)")
        start_info = event.get("start", {})
        date_time = start_info.get("dateTime")

        if date_time:
            try:
                when = datetime.fromisoformat(date_time).strftime(
                    "%a %b %d, %-I:%M %p"
                )
            except ValueError:
                when = date_time
        else:
            # All-day event — only a "date" key is present, no time.
            date_only = start_info.get("date", "")
            try:
                when = (
                    datetime.fromisoformat(date_only).strftime("%a %b %d")
                    + " (all day)"
                )
            except ValueError:
                when = date_only or "(unknown date)"

        return f"- {when}: {summary}"

    @staticmethod
    def _parse_event_start(event: dict) -> datetime | None:
        start_info = event.get("start", {})
        raw_start = start_info.get("dateTime") or start_info.get("date")

        if not raw_start:
            return None

        if raw_start.endswith("Z"):
            raw_start = raw_start[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(raw_start)
        except ValueError:
            return None

        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)

        return parsed
