"""Tests for working out where EON is.

The network is always injected, so every path — cache hits, stale
caches, provider failures — is exercised without a real lookup. That
matters here more than usual: no IP-geolocation provider is reachable
from the test sandbox, so these tests are the only evidence the logic
works.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.modules.automation.location import (
    Location,
    LocationResolver,
    detect_location,
    parse_location_payload,
)
from src.modules.automation.weather import WeatherTool

# --- parsing what the providers actually return -----------------------------

IPAPI_PAYLOAD = {
    "ip": "203.0.113.7",
    "city": "Bangalore",
    "region": "Karnataka",
    "country_name": "India",
    "latitude": 12.9716,
    "longitude": 77.5946,
}

IPWHOIS_PAYLOAD = {
    "ip": "203.0.113.7",
    "success": True,
    "city": "Bangalore",
    "region": "Karnataka",
    "country": "India",
    "latitude": 12.9716,
    "longitude": 77.5946,
}

IPINFO_PAYLOAD = {
    "ip": "203.0.113.7",
    "city": "Bangalore",
    "region": "Karnataka",
    "country": "IN",
    "loc": "12.9716,77.5946",
}


def test_parses_the_ipapi_shape():
    assert parse_location_payload(IPAPI_PAYLOAD) == ("Bangalore", 12.9716, 77.5946)


def test_parses_the_ipwhois_shape():
    assert parse_location_payload(IPWHOIS_PAYLOAD) == ("Bangalore", 12.9716, 77.5946)


def test_parses_the_ipinfo_shape_where_both_coordinates_are_one_string():
    assert parse_location_payload(IPINFO_PAYLOAD) == ("Bangalore", 12.9716, 77.5946)


def test_parses_coordinates_given_as_strings():
    payload = {"city": "Bangalore", "latitude": "12.9716", "longitude": "77.5946"}

    assert parse_location_payload(payload) == ("Bangalore", 12.9716, 77.5946)


def test_a_failed_lookup_is_not_a_location():
    # ipwho.is signals failure with success=false rather than a status.
    assert parse_location_payload({"success": False, "message": "reserved range"}) is None


def test_a_reply_without_a_city_is_rejected():
    assert parse_location_payload({"latitude": 1.0, "longitude": 2.0}) is None


def test_a_reply_without_coordinates_is_rejected():
    assert parse_location_payload({"city": "Bangalore"}) is None


def test_a_reply_that_is_not_an_object_is_rejected():
    assert parse_location_payload(["Bangalore"]) is None
    assert parse_location_payload("Bangalore") is None
    assert parse_location_payload(None) is None


def test_a_region_is_used_when_there_is_no_city():
    payload = {"region": "Karnataka", "latitude": 12.97, "longitude": 77.59}

    assert parse_location_payload(payload) == ("Karnataka", 12.97, 77.59)


# --- trying the providers in turn -------------------------------------------


def test_the_first_provider_that_answers_wins():
    calls: list[str] = []

    def fetcher(url: str) -> dict:
        calls.append(url)
        return IPAPI_PAYLOAD

    location = detect_location(fetcher)

    assert location is not None
    assert location.name == "Bangalore"
    assert len(calls) == 1


def test_a_failing_provider_falls_through_to_the_next():
    def fetcher(url: str) -> dict:
        if "ipapi" in url:
            raise RuntimeError("down")
        return IPWHOIS_PAYLOAD

    location = detect_location(fetcher)

    assert location is not None
    assert location.name == "Bangalore"


def test_an_unusable_reply_also_falls_through():
    def fetcher(url: str) -> dict:
        if "ipapi" in url:
            return {"success": False}
        return IPINFO_PAYLOAD

    location = detect_location(fetcher)

    assert location is not None
    assert location.name == "Bangalore"


def test_every_provider_failing_yields_nothing():
    def fetcher(url: str) -> dict:
        raise RuntimeError("no network")

    assert detect_location(fetcher) is None


def test_the_detected_location_records_its_source():
    location = detect_location(lambda url: IPAPI_PAYLOAD)

    assert location is not None
    assert location.source == "detected"


# --- the resolver -----------------------------------------------------------

FALLBACK = Location("New Delhi", 28.6139, 77.209, "fallback")
CONFIGURED = Location("Indore", 22.7196, 75.8577, "configured")


def _resolver(tmp_path, detector, **kwargs) -> LocationResolver:
    return LocationResolver(
        cache_path=tmp_path / "location.json",
        fallback=FALLBACK,
        detector=detector,
        **kwargs,
    )


def _bangalore() -> Location:
    return Location("Bangalore", 12.9716, 77.5946, "detected")


def test_a_configured_place_beats_detection(tmp_path):
    def detector():
        raise AssertionError("detection should not run when a place is configured")

    resolver = _resolver(tmp_path, detector, configured=CONFIGURED)

    assert resolver.resolve() == CONFIGURED


def test_detection_is_used_when_nothing_is_configured(tmp_path):
    assert _resolver(tmp_path, _bangalore).resolve().name == "Bangalore"


def test_a_detection_is_cached_for_next_time(tmp_path):
    calls = {"n": 0}

    def detector():
        calls["n"] += 1
        return _bangalore()

    first = _resolver(tmp_path, detector)
    assert first.resolve().name == "Bangalore"

    # A fresh resolver over the same cache file, as on the next launch.
    second = _resolver(tmp_path, detector)
    resolved = second.resolve()

    assert resolved.name == "Bangalore"
    assert resolved.source == "cached"
    assert calls["n"] == 1, "a cached detection should not be repeated"


def test_a_detection_is_only_made_once_per_run(tmp_path):
    calls = {"n": 0}

    def detector():
        calls["n"] += 1
        return _bangalore()

    resolver = _resolver(tmp_path, detector)

    for _ in range(5):
        resolver.resolve()

    assert calls["n"] == 1


def test_a_stale_cache_is_refreshed(tmp_path):
    # A detection from three days ago, with a one-day lifetime.
    stale = _resolver(tmp_path, _bangalore, cache_hours=24)
    stale.resolve()

    moved = _resolver(tmp_path, lambda: Location("Bangalore", 1.0, 2.0, "detected"))
    # Rewrite the timestamp to make the stored detection old.
    import json

    path = tmp_path / "location.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["detected_at"] = (datetime.now() - timedelta(days=3)).isoformat(
        timespec="seconds"
    )
    path.write_text(json.dumps(data), encoding="utf-8")

    resolved = moved.resolve()

    assert resolved.source == "detected"
    assert resolved.latitude == 1.0


def test_moving_city_is_picked_up_after_the_cache_expires(tmp_path):
    first = _resolver(tmp_path, _bangalore, cache_hours=0)
    assert first.resolve().name == "Bangalore"

    # cache_hours=0 means nothing is ever fresh, so the next run
    # re-detects — which is what happens after a move.
    moved = _resolver(
        tmp_path, lambda: Location("Bangalore", 12.97, 77.59, "detected"), cache_hours=0
    )

    assert moved.resolve().name == "Bangalore"


def test_a_stale_cache_beats_nothing_when_detection_fails(tmp_path):
    fresh = _resolver(tmp_path, _bangalore, cache_hours=24)
    fresh.resolve()

    def broken():
        raise RuntimeError("no network")

    offline = _resolver(tmp_path, broken, cache_hours=0)
    resolved = offline.resolve()

    assert resolved.name == "Bangalore"
    assert resolved.source == "cached"


def test_the_fallback_is_used_when_nothing_works(tmp_path):
    def broken():
        raise RuntimeError("no network")

    assert _resolver(tmp_path, broken).resolve() == FALLBACK


def test_a_detector_returning_nothing_is_handled(tmp_path):
    assert _resolver(tmp_path, lambda: None).resolve() == FALLBACK


def test_a_corrupt_cache_file_is_ignored(tmp_path):
    path = tmp_path / "location.json"
    path.write_text("{ not json", encoding="utf-8")

    assert _resolver(tmp_path, _bangalore).resolve().name == "Bangalore"


def test_a_cache_file_missing_fields_is_ignored(tmp_path):
    path = tmp_path / "location.json"
    path.write_text('{"name": "Bangalore"}', encoding="utf-8")

    assert _resolver(tmp_path, _bangalore).resolve().name == "Bangalore"


# --- how the weather tool uses all this -------------------------------------


def test_a_configured_city_is_used_as_here():
    tool = WeatherTool(default_location_name="Indore", default_latitude=22.7196, default_longitude=75.8577)

    assert tool._default_location() == CONFIGURED


def test_coordinates_alone_are_enough_to_configure_a_place():
    tool = WeatherTool(default_latitude=22.7196, default_longitude=75.8577)

    location = tool._default_location()

    assert location.source == "configured"
    assert location.latitude == 22.7196


def test_with_nothing_configured_the_detected_place_is_used(tmp_path):
    tool = WeatherTool(location_resolver=_resolver(tmp_path, _bangalore))

    assert tool._default_location().name == "Bangalore"


def test_detection_can_be_switched_off(tmp_path):
    def detector():
        raise AssertionError("detection should be off")

    tool = WeatherTool(
        auto_detect_location=False,
        location_resolver=_resolver(tmp_path, detector),
    )

    assert tool._default_location() == FALLBACK


def test_here_is_returned_when_no_city_is_named(tmp_path):
    tool = WeatherTool(location_resolver=_resolver(tmp_path, _bangalore))

    latitude, longitude, name = tool._resolve_location("what is the weather")

    assert name == "Bangalore"
    assert (latitude, longitude) == (12.9716, 77.5946)


def test_a_named_city_still_wins_over_here(tmp_path):
    # "weather in Mumbai" must not be answered with the detected city.
    tool = WeatherTool(location_resolver=_resolver(tmp_path, _bangalore))

    assert tool._extract_city("weather in Mumbai") == "Mumbai"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what's the weather", ""),
        ("mausam kaisa hai", ""),
        ("weather in Mumbai", "Mumbai"),
        ("mausam kaisa hai Jaipur mein", "Jaipur"),
    ],
)
def test_city_extraction_is_unchanged(text, expected):
    assert WeatherTool._extract_city(text) == expected
