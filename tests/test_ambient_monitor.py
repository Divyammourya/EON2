from datetime import datetime, timedelta

from src.modules.monitor.ambient import AmbientMonitor, CalendarAmbientSource
from src.modules.monitor.config import AmbientMonitorConfig
from src.modules.monitor.models import AmbientSignal


class FakeSource:
    def __init__(self) -> None:
        self.calls = 0

    def scan(self):
        self.calls += 1
        return [
            AmbientSignal(
                id="signal-1",
                kind="test",
                title="Test",
                message="Something happened.",
            )
        ]


class FakeCalendar:
    def __init__(self, start_at: datetime) -> None:
        self.start_at = start_at

    def list_events_between(self, start: datetime, end: datetime):
        return [
            {
                "id": "meeting-1",
                "summary": "Standup",
                "start_at": self.start_at,
            }
        ]


def test_ambient_monitor_deduplicates_signals() -> None:
    source = FakeSource()
    monitor = AmbientMonitor(
        config=AmbientMonitorConfig(signal_cooldown_minutes=30),
        sources=[source],
    )

    assert len(monitor.scan()) == 1
    assert monitor.scan() == []
    assert source.calls == 2


def test_calendar_source_reports_events_inside_warning_window() -> None:
    source = CalendarAmbientSource(
        calendar_tool=FakeCalendar(datetime.now() + timedelta(minutes=4)),
        warning_minutes=5,
        lookahead_minutes=10,
    )

    signals = source.scan()

    assert len(signals) == 1
    assert signals[0].kind == "calendar.upcoming"
    assert "Standup" in signals[0].message
