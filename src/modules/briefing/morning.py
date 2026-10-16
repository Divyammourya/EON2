"""EON's morning briefing.

On the first launch of the day, inside a configurable morning window
(6am-10am by default), EON greets the user with the weather for their
area: temperature, humidity and air quality.

Design notes:
    - "First launch of the day" is remembered in a tiny JSON file rather
      than in memory, because the whole point is for it to survive the
      restart that makes it the first launch of the day.
    - The wording is assembled from the readings rather than written by
      the language model. The numbers in a weather briefing have to be
      right, and a small model is quite capable of turning 24 degrees
      into "about twenty" or inventing a shower that isn't there. The
      character comes from picking an opener that fits the conditions,
      so it can never contradict the figures sitting next to it.
    - A failed fetch is allowed to fail quietly. The date is only
      recorded once a briefing has actually been spoken, so a launch
      later in the same window gets another go.

Requires: Python 3.12+
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from src.core.logger import get_logger
from src.modules.automation.weather import WeatherReadings

logger = get_logger("Briefing")

DEFAULT_START_HOUR = 6
DEFAULT_END_HOUR = 10


def should_brief(
    now: datetime,
    last_briefed: str | None,
    *,
    start_hour: int = DEFAULT_START_HOUR,
    end_hour: int = DEFAULT_END_HOUR,
) -> bool:
    """Whether a morning briefing is due.

    Args:
        now: The current local time.
        last_briefed: ISO date (``YYYY-MM-DD``) of the last briefing, or
            ``None`` if there has never been one.
        start_hour: First hour of the morning window, inclusive.
        end_hour: Hour the morning window ends, exclusive.

    Returns:
        ``True`` on the first launch of the day inside the window.
    """
    if not start_hour <= now.hour < end_hour:
        return False

    return last_briefed != now.date().isoformat()


def _salutation(now: datetime) -> str:
    """A time-appropriate greeting.

    Args:
        now: The time being greeted.

    Returns:
        "Good morning", "Good afternoon" or "Good evening".
    """
    if now.hour < 12:
        return "Good morning"
    if now.hour < 17:
        return "Good afternoon"
    return "Good evening"


def _opener(readings: WeatherReadings) -> str:
    """A short remark that fits the conditions.

    This is where the character comes from. It is chosen from the
    readings rather than written by a model, so it is guaranteed not to
    describe weather that isn't happening.

    Args:
        readings: The current conditions.

    Returns:
        A clause suitable for following the salutation.
    """
    if readings.is_wet:
        return "looks like a wet one out there"

    if readings.temperature_c >= 38:
        return "it's going to be a scorcher"

    if readings.temperature_c >= 32:
        return "it's a hot one today"

    if readings.temperature_c <= 8:
        return "cold enough to think twice about going out"

    if readings.air_quality_index is not None and readings.air_quality_index > 150:
        return "the air is rough this morning, so go easy out there"

    return "here's how things look outside"


def build_briefing(
    readings: WeatherReadings,
    now: datetime | None = None,
) -> str:
    """Composes the spoken briefing from a set of readings.

    Args:
        readings: The current conditions.
        now: The time being briefed for. Defaults to the current time.

    Returns:
        The full text to speak.
    """
    moment = now or datetime.now()

    sentences = [f"{_salutation(moment)}, {_opener(readings)}."]

    condition = (
        f"It's {readings.temperature_c:.0f} degrees and "
        f"{readings.description} in {readings.location_name}"
    )

    # Only mention the apparent temperature when it actually differs —
    # "feels like 24, and it is 24" is noise.
    if readings.feels_like_c - readings.temperature_c >= 2:
        condition += f", and it feels closer to {readings.feels_like_c:.0f}"
    elif readings.temperature_c - readings.feels_like_c >= 2:
        condition += f", though it feels closer to {readings.feels_like_c:.0f}"

    sentences.append(condition + ".")

    if readings.humidity_percent is not None:
        sentences.append(f"Humidity is {readings.humidity_percent:.0f} percent.")

    if readings.air_quality_description is not None:
        sentences.append(f"Air quality is {readings.air_quality_description}.")

    return " ".join(sentences)


class MorningBriefing:
    """Builds and delivers the first briefing of the day.

    Attributes:
        _readings_provider: Zero-argument callable returning the current
            :class:`WeatherReadings` for the configured location.
        _state_path: Where the last-briefed date is remembered.
        _start_hour: First hour of the morning window.
        _end_hour: Hour the morning window ends.
        _enabled: Whether briefings happen at all.
    """

    def __init__(
        self,
        readings_provider: Callable[[], WeatherReadings],
        state_path: str | Path,
        *,
        start_hour: int = DEFAULT_START_HOUR,
        end_hour: int = DEFAULT_END_HOUR,
        enabled: bool = True,
    ) -> None:
        self._readings_provider = readings_provider
        self._state_path = Path(state_path)
        self._start_hour = start_hour
        self._end_hour = end_hour
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        """Whether morning briefings are switched on."""
        return self._enabled

    def last_briefed(self) -> str | None:
        """The ISO date of the last briefing, or ``None``.

        Any unreadable or malformed state file is treated as "never
        briefed" rather than raising — the worst case is one extra
        briefing, which is much better than EON refusing to start.
        """
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

        value = data.get("last_briefed") if isinstance(data, dict) else None
        return str(value) if value else None

    def _record(self, day: str) -> None:
        """Remembers that a briefing happened on ``day``."""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(
                json.dumps({"last_briefed": day}, indent=2),
                encoding="utf-8",
            )
        except OSError:
            logger.warning(
                "Could not record the briefing date in %s; EON may brief "
                "again next launch.",
                self._state_path,
            )

    def greeting(self, now: datetime | None = None) -> str | None:
        """The briefing to speak now, or ``None`` if none is due.

        Never raises. A briefing is a nicety, and a missing one must not
        be what stops EON starting up.

        Args:
            now: The time to check against. Defaults to the current time.

        Returns:
            The text to speak, or ``None`` when no briefing is due, the
            feature is off, or the weather could not be fetched.
        """
        if not self._enabled:
            return None

        moment = now or datetime.now()

        if not should_brief(
            moment,
            self.last_briefed(),
            start_hour=self._start_hour,
            end_hour=self._end_hour,
        ):
            return None

        try:
            readings = self._readings_provider()
        except Exception as error:
            # Deliberately not recorded, so a later launch today — still
            # inside the window — gets another attempt.
            logger.warning("Skipping the morning briefing: %s", error)
            return None

        text = build_briefing(readings, moment)
        self._record(moment.date().isoformat())
        logger.info("Morning briefing delivered for %s.", readings.location_name)
        return text
