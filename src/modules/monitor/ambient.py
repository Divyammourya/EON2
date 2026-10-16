"""
Ambient awareness monitoring.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from src.core.logger import get_logger
from src.modules.monitor.config import AmbientMonitorConfig
from src.modules.monitor.models import AmbientSignal

logger = get_logger("Monitor.Ambient")


class AmbientSource(Protocol):
    """Produces ambient signals from one area of the computer."""

    def scan(self) -> list[AmbientSignal]:
        """Return newly observed signals."""
        ...


class AmbientMonitor:
    """
    Coordinates ambient awareness sources and applies de-duplication.
    """

    def __init__(
        self,
        config: AmbientMonitorConfig,
        sources: list[AmbientSource],
    ) -> None:
        self._config = config
        self._sources = sources
        self._seen_until: dict[str, datetime] = {}

    def scan(self) -> list[AmbientSignal]:
        if not self._config.enabled:
            return []

        now = datetime.now()
        self._expire_seen(now)

        signals: list[AmbientSignal] = []

        for source in self._sources:
            try:
                for signal in source.scan():
                    if signal.id in self._seen_until:
                        continue

                    self._seen_until[signal.id] = now + timedelta(
                        minutes=self._config.signal_cooldown_minutes,
                    )
                    signals.append(signal)
            except Exception:
                logger.exception("Ambient source %s failed.", source.__class__.__name__)

        return signals

    def _expire_seen(self, now: datetime) -> None:
        expired = [
            signal_id
            for signal_id, expires_at in self._seen_until.items()
            if expires_at <= now
        ]

        for signal_id in expired:
            del self._seen_until[signal_id]


class DownloadAmbientSource:
    """
    Notices newly completed files in the Downloads folder.
    """

    _TEMP_SUFFIXES = (".crdownload", ".part", ".tmp", ".download")

    def __init__(self, downloads_path: Path) -> None:
        self._downloads_path = downloads_path
        self._known_files = self._snapshot_completed_files()

    def scan(self) -> list[AmbientSignal]:
        current_files = self._snapshot_completed_files()
        new_files = current_files - self._known_files
        self._known_files = current_files

        signals: list[AmbientSignal] = []

        for path in sorted(new_files, key=lambda item: item.name.lower()):
            signals.append(
                AmbientSignal(
                    id=f"download:{path.resolve()}",
                    kind="download.completed",
                    title="Download finished",
                    message=f"Your download finished: {path.name}.",
                    metadata={"path": str(path)},
                )
            )

        return signals

    def _snapshot_completed_files(self) -> set[Path]:
        if not self._downloads_path.exists():
            return set()

        completed: set[Path] = set()

        for path in self._downloads_path.iterdir():
            if not path.is_file():
                continue

            if path.suffix.lower() in self._TEMP_SUFFIXES:
                continue

            completed.add(path)

        return completed


class CalendarAmbientSource:
    """
    Notices calendar events that are about to start.
    """

    def __init__(
        self,
        calendar_tool,
        warning_minutes: int,
        lookahead_minutes: int,
    ) -> None:
        self._calendar_tool = calendar_tool
        self._warning_minutes = warning_minutes
        self._lookahead_minutes = lookahead_minutes

    def scan(self) -> list[AmbientSignal]:
        can_read_silently = getattr(self._calendar_tool, "can_read_silently", None)

        if can_read_silently is not None and not can_read_silently():
            return []

        now = datetime.now()
        lookahead = now + timedelta(minutes=self._lookahead_minutes)

        events = self._calendar_tool.list_events_between(now, lookahead)
        signals: list[AmbientSignal] = []

        for event in events:
            start = event.get("start_at")

            if not isinstance(start, datetime):
                continue

            minutes_until = int((start - now).total_seconds() // 60)

            if minutes_until < 0 or minutes_until > self._warning_minutes:
                continue

            title = event.get("summary") or "calendar event"
            event_id = event.get("id") or f"{title}:{start.isoformat()}"

            signals.append(
                AmbientSignal(
                    id=f"calendar:{event_id}:{start.isoformat()}",
                    kind="calendar.upcoming",
                    title="Meeting soon",
                    message=(
                        f"{title} starts "
                        f"{'now' if minutes_until == 0 else f'in {minutes_until} minutes'}."
                    ),
                    metadata={"event": event},
                )
            )

        return signals


class HungWindowAmbientSource:
    """
    Notices visible Windows applications that stop responding.
    """

    def scan(self) -> list[AmbientSignal]:
        try:
            import win32gui
        except ImportError:
            return []

        signals: list[AmbientSignal] = []

        def visit(hwnd: int, _extra) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return

            title = win32gui.GetWindowText(hwnd).strip()

            if not title:
                return

            try:
                is_hung = bool(win32gui.IsHungAppWindow(hwnd))
            except Exception:
                return

            if not is_hung:
                return

            signals.append(
                AmbientSignal(
                    id=f"hung_window:{hwnd}:{title}",
                    kind="window.hung",
                    title="App not responding",
                    message=f"{title} appears to be not responding.",
                    severity="warning",
                    metadata={"hwnd": hwnd, "title": title},
                )
            )

        win32gui.EnumWindows(visit, None)

        return signals
