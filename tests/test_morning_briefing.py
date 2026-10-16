"""Tests for the morning briefing.

Pure logic plus a temp-file state store — no network, no audio. The
readings are constructed directly so the wording can be checked against
exact numbers.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.modules.automation.weather import WeatherReadings, describe_air_quality
from src.modules.briefing.morning import (
    MorningBriefing,
    build_briefing,
    should_brief,
)

AT_7AM = datetime(2026, 10, 17, 7, 0)
AT_5AM = datetime(2026, 10, 17, 5, 0)
AT_11AM = datetime(2026, 10, 17, 11, 0)


def _readings(**overrides) -> WeatherReadings:
    """A mild, pleasant morning, with anything overridable."""
    base = {
        "location_name": "Indore",
        "temperature_c": 24.0,
        "feels_like_c": 24.0,
        "humidity_percent": 41.0,
        "wind_kph": 7.0,
        "weather_code": 0,
        "air_quality_index": 62.0,
        "pm2_5": 18.0,
    }
    base.update(overrides)
    return WeatherReadings(**base)


# --- when a briefing is due -------------------------------------------------


def test_first_launch_in_the_window_is_due():
    assert should_brief(AT_7AM, None) is True


def test_the_window_is_inclusive_of_the_start_hour():
    assert should_brief(datetime(2026, 10, 17, 6, 0), None) is True


def test_the_window_excludes_the_end_hour():
    assert should_brief(datetime(2026, 10, 17, 10, 0), None) is False


def test_too_early_is_not_due():
    assert should_brief(AT_5AM, None) is False


def test_too_late_is_not_due():
    assert should_brief(AT_11AM, None) is False


def test_a_second_launch_the_same_day_is_not_due():
    assert should_brief(AT_7AM, "2026-10-17") is False


def test_yesterdays_briefing_does_not_count():
    assert should_brief(AT_7AM, "2026-10-16") is True


def test_the_window_is_configurable():
    assert should_brief(datetime(2026, 10, 17, 5, 0), None, start_hour=4, end_hour=6) is True


# --- the wording ------------------------------------------------------------


def test_the_briefing_carries_the_facts():
    text = build_briefing(_readings(), AT_7AM)

    assert text.startswith("Good morning")
    assert "24 degrees" in text
    assert "clear sky" in text
    assert "Indore" in text
    assert "41 percent" in text
    assert "moderate" in text


def test_apparent_temperature_is_omitted_when_it_barely_differs():
    # "feels like 24, and it is 24" is noise.
    assert "feels closer" not in build_briefing(_readings(), AT_7AM)


def test_apparent_temperature_is_mentioned_when_it_differs():
    text = build_briefing(_readings(temperature_c=24.0, feels_like_c=31.0), AT_7AM)

    assert "feels closer to 31" in text


def test_missing_humidity_is_simply_left_out():
    text = build_briefing(_readings(humidity_percent=None), AT_7AM)

    assert "Humidity" not in text
    assert "24 degrees" in text


def test_missing_air_quality_is_simply_left_out():
    text = build_briefing(_readings(air_quality_index=None), AT_7AM)

    assert "Air quality" not in text


def test_rain_gets_a_wet_opener():
    assert "wet one" in build_briefing(_readings(weather_code=63), AT_7AM)


def test_a_very_hot_day_gets_a_scorcher_opener():
    assert "scorcher" in build_briefing(_readings(temperature_c=40.0), AT_7AM)


def test_a_cold_day_gets_a_cold_opener():
    assert "cold enough" in build_briefing(_readings(temperature_c=5.0), AT_7AM)


def test_bad_air_gets_an_air_opener():
    text = build_briefing(_readings(air_quality_index=180.0), AT_7AM)

    assert "air is rough" in text


def test_the_salutation_follows_the_hour():
    assert build_briefing(_readings(), datetime(2026, 10, 17, 14, 0)).startswith(
        "Good afternoon"
    )
    assert build_briefing(_readings(), datetime(2026, 10, 17, 19, 0)).startswith(
        "Good evening"
    )


# --- the air quality bands --------------------------------------------------


@pytest.mark.parametrize(
    "index,expected",
    [
        (10, "good"),
        (50, "good"),
        (51, "moderate"),
        (100, "moderate"),
        (120, "unhealthy for sensitive groups"),
        (180, "unhealthy"),
        (250, "very unhealthy"),
        (400, "hazardous"),
    ],
)
def test_air_quality_bands(index, expected):
    assert describe_air_quality(index) == expected


# --- the service ------------------------------------------------------------


def _briefing(tmp_path, provider, **kwargs) -> MorningBriefing:
    return MorningBriefing(
        readings_provider=provider,
        state_path=tmp_path / "briefing.json",
        **kwargs,
    )


def test_the_briefing_is_delivered_once_a_day(tmp_path):
    briefing = _briefing(tmp_path, _readings)

    assert briefing.last_briefed() is None

    first = briefing.greeting(AT_7AM)

    assert first is not None
    assert briefing.last_briefed() == "2026-10-17"

    # Second launch, same day, same window.
    assert briefing.greeting(AT_7AM) is None


def test_nothing_is_said_outside_the_window(tmp_path):
    briefing = _briefing(tmp_path, _readings)

    assert briefing.greeting(AT_11AM) is None
    assert briefing.last_briefed() is None


def test_disabling_it_says_nothing(tmp_path):
    briefing = _briefing(tmp_path, _readings, enabled=False)

    assert briefing.greeting(AT_7AM) is None
    assert briefing.last_briefed() is None


def test_a_failed_fetch_does_not_burn_the_day(tmp_path):
    def failing():
        raise RuntimeError("no network")

    briefing = _briefing(tmp_path, failing)

    assert briefing.greeting(AT_7AM) is None
    # Not recorded, so a later launch today still gets a go.
    assert briefing.last_briefed() is None


def test_a_later_launch_after_a_failure_still_briefs(tmp_path):
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("no network")
        return _readings()

    briefing = _briefing(tmp_path, flaky)

    assert briefing.greeting(AT_7AM) is None
    assert briefing.greeting(datetime(2026, 10, 17, 9, 0)) is not None


def test_a_corrupt_state_file_is_treated_as_never_briefed(tmp_path):
    path = tmp_path / "briefing.json"
    path.write_text("{ this is not json", encoding="utf-8")

    briefing = _briefing(tmp_path, _readings)

    assert briefing.last_briefed() is None
    assert briefing.greeting(AT_7AM) is not None


def test_the_state_file_survives_a_restart(tmp_path):
    first = _briefing(tmp_path, _readings)
    assert first.greeting(AT_7AM) is not None

    # A fresh instance reading the same file, as on the next launch.
    second = _briefing(tmp_path, _readings)

    assert second.last_briefed() == "2026-10-17"
    assert second.greeting(AT_7AM) is None


def test_the_window_can_be_moved(tmp_path):
    briefing = _briefing(tmp_path, _readings, start_hour=4, end_hour=6)

    assert briefing.greeting(datetime(2026, 10, 17, 5, 0)) is not None
    assert briefing.greeting(AT_7AM) is None
