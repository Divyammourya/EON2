"""
Proactive Speech Configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProactiveServiceConfig:
    """
    Configuration for the Proactive Speech subsystem.

    Attributes:
        enabled: Master switch. If ``False``, the background thread
            still runs (so toggling this at runtime is cheap) but never
            speaks anything.
        check_interval_seconds: How often the background loop wakes up
            to check for due reminders / idle check-ins. Lower values
            mean reminders fire closer to their exact due time, at the
            cost of a bit more CPU wakeup churn.
        idle_checkin_minutes: How long EON should go without any
            interaction (text or voice) before it speaks up on its
            own. ``None`` disables idle check-ins entirely while still
            allowing explicit reminders via ``remind_at``.
        idle_checkin_message: What EON says when the idle threshold is
            crossed.
    """

    enabled: bool = True
    check_interval_seconds: float = 15.0
    idle_checkin_minutes: float | None = 10.0
    idle_checkin_message: str = (
        "Just checking in, sir. Let me know if there's anything you need."
    )
