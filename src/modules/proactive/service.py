"""
Proactive Speech Service.

Lets EON speak up unprompted: scheduled reminders and idle
check-ins, both delivered through the existing ``VoiceService`` on a
background thread.

Mirrors the shape of ``VoiceService``/``MemoryService``: a single
high-level entry point, with all threading and timing detail hidden
behind a small surface (``remind_at``, ``notify_interaction``).
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from uuid import UUID

from src.core.logger import get_logger
from src.modules.proactive.config import ProactiveServiceConfig
from src.modules.proactive.models import Reminder
from src.modules.voice.exceptions import VoiceError
from src.modules.voice.service import VoiceService
from src.modules.monitor import MonitorManager

logger = get_logger("Proactive")


class ProactiveService:
    """
    Background scheduler that speaks unprompted through ``VoiceService``.

    Two triggers are supported today:
        - **Reminders**: one-off, scheduled via ``remind_at``.
        - **Idle check-ins**: fires once after
          ``config.idle_checkin_minutes`` of silence, and won't fire
          again until another interaction happens first (so it never
          nags on a loop).

    Both respect barge-in: a tick never speaks while EON is already
    speaking (``voice.is_speaking``) or while no voice session is open
    (``voice.default_session_id``); it simply waits for the next tick.
    """

    def __init__(
        self,
        voice: VoiceService,
        config: ProactiveServiceConfig,
        monitor: MonitorManager | None = None,
    ) -> None:
        self._voice = voice
        self._config = config
        self._monitor = monitor

        self._reminders: dict[UUID, Reminder] = {}
        self._reminders_lock = threading.Lock()

        self._last_interaction_at = datetime.now()
        self._last_ambient_scan_at: datetime | None = None
        self._idle_checkin_done = False

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        logger.info("Proactive Service initialized.")

    def initialize(self) -> None:
        """No heavyweight setup needed; the thread starts in ``start``."""

    def shutdown(self) -> None:
        """Stops the background thread and drops any pending reminders."""
        self.stop()

        with self._reminders_lock:
            self._reminders.clear()

    def health_check(self) -> bool:
        """Healthy as long as the background loop is running (or was
        never asked to run, e.g. ``enabled=False``)."""
        return self._thread is None or self._thread.is_alive()

    def start(self) -> None:
        """Starts the background scheduling thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="EON-ProactiveSpeech",
            daemon=True,
        )
        self._thread.start()

        logger.info("Proactive Speech loop started.")

    def stop(self) -> None:
        """Stops the background scheduling thread."""
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join(timeout=self._config.check_interval_seconds + 5)
            self._thread = None

        logger.info("Proactive Speech loop stopped.")

    def notify_interaction(self) -> None:
        """
        Tells the scheduler a real interaction just happened.

        Call this after every turn (typed, ``listen``, or wake-word),
        both to reset the idle-checkin clock and to re-arm it so it can
        fire again after the *next* quiet stretch.
        """
        self._last_interaction_at = datetime.now()
        self._last_ambient_scan_at = None
        self._idle_checkin_done = False

    def remind_at(self, message: str, due_at: datetime) -> UUID:
        """
        Schedules a one-off spoken reminder.

        Args:
            message: The exact text EON will speak when it fires.
            due_at: When the reminder becomes due. If this is already
                in the past, it fires on the very next tick.

        Returns:
            The reminder's id, usable with ``cancel_reminder``.
        """
        reminder = Reminder(message=message, due_at=due_at)

        with self._reminders_lock:
            self._reminders[reminder.id] = reminder

        logger.info("Scheduled reminder %s for %s.", reminder.id, due_at.isoformat())

        return reminder.id

    def remind_in(self, message: str, minutes: float) -> UUID:
        """Convenience wrapper: schedules a reminder ``minutes`` from now."""
        return self.remind_at(message, datetime.now() + timedelta(minutes=minutes))

    def cancel_reminder(self, reminder_id: UUID) -> bool:
        """
        Cancels a pending reminder.

        Returns:
            ``True`` if a reminder with that id was pending and removed,
            ``False`` if it wasn't found (already fired or unknown id).
        """
        with self._reminders_lock:
            return self._reminders.pop(reminder_id, None) is not None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                logger.exception("Proactive Speech tick failed; continuing.")

            self._stop_event.wait(self._config.check_interval_seconds)

    def _tick(self) -> None:
        if not self._config.enabled:
            return

        session_id = self._voice.default_session_id

        if session_id is None or self._voice.is_speaking:
            # No open session to speak through, or EON's already
            # mid-sentence — never talk over the user or an existing
            # reply. Just wait for the next tick.
            return

        self._speak_due_reminders(session_id)
        self._speak_ambient_signals(session_id)
        self._speak_idle_checkin(session_id)

    def _speak_due_reminders(self, session_id: UUID) -> None:
        now = datetime.now()

        with self._reminders_lock:
            due = [r for r in self._reminders.values() if r.due_at <= now]
            for reminder in due:
                del self._reminders[reminder.id]

        for reminder in due:
            self._say(session_id, reminder.message)

    def _speak_idle_checkin(self, session_id: UUID) -> None:
        threshold = self._config.idle_checkin_minutes

        if threshold is None or self._idle_checkin_done:
            return

        idle_for = datetime.now() - self._last_interaction_at

        if idle_for >= timedelta(minutes=threshold):
            self._idle_checkin_done = True
            self._say(session_id, self._config.idle_checkin_message)

    def _speak_ambient_signals(self, session_id: UUID) -> None:
        if self._monitor is None:
            return

        now = datetime.now()

        if self._last_ambient_scan_at is not None:
            elapsed = (now - self._last_ambient_scan_at).total_seconds()
            if elapsed < self._monitor.ambient_check_interval_seconds:
                return

        self._last_ambient_scan_at = now

        for signal in self._monitor.scan_ambient():
            self._say(session_id, signal.message)

    def _say(self, session_id: UUID, message: str) -> None:
        try:
            self._voice.say(session_id, message)
            logger.info("Spoke proactively: %s", message)
        except VoiceError as exc:
            logger.warning("Proactive speech failed: %s", exc)
