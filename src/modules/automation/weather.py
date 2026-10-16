"""
Weather Tool.

Answers real-time weather/temperature questions using Open-Meteo
(https://open-meteo.com), a free weather API that requires no API key
and no account. Also answers plain date/time questions locally (no
network call needed for those — the system clock is the source of
truth).

Requires network access. Uses `httpx`, already a project dependency
(pulled in transitively for the Ollama/Google clients) — no new
package is needed for this tool.
"""

from __future__ import annotations

from datetime import datetime

import httpx

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_REQUEST_TIMEOUT_SECONDS = 6.0

# Fallback location used when the user doesn't name a city and no
# default has been configured (see VoiceServiceConfig-adjacent
# settings in config/settings.json: weather_location_name /
# weather_latitude / weather_longitude). New Delhi is used as a
# reasonable default given the Hindi/Hinglish support added alongside
# this tool — change it in settings.json to your actual city.
_DEFAULT_LOCATION_NAME = "New Delhi"
_DEFAULT_LATITUDE = 28.6139
_DEFAULT_LONGITUDE = 77.2090

# Open-Meteo's WMO weather codes, condensed into plain-language
# descriptions. Not exhaustive of every WMO code, but covers the
# common ones; unrecognized codes fall back to "changing conditions".
_WEATHER_CODE_DESCRIPTIONS = {
    0: "clear sky",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "foggy with icy fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "light rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "light snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "light rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "a thunderstorm",
    96: "a thunderstorm with light hail",
    99: "a thunderstorm with heavy hail",
}


class WeatherTool(Tool):
    """Tool for real-time weather/temperature and local date/time."""

    def __init__(
        self,
        default_location_name: str = _DEFAULT_LOCATION_NAME,
        default_latitude: float = _DEFAULT_LATITUDE,
        default_longitude: float = _DEFAULT_LONGITUDE,
    ) -> None:
        self._default_location_name = default_location_name
        self._default_latitude = default_latitude
        self._default_longitude = default_longitude

    @property
    def name(self) -> str:
        return "weather"

    def execute(self, command: str = "") -> ToolResult:
        text = (command or "").strip().lower()

        wants_time_or_date = any(
            word in text
            for word in ("time", "date", "day", "baje", "tareekh", " din ")
        ) and not any(word in text for word in ("weather", "temperature", "mausam", "tapman"))

        if wants_time_or_date and "weather" not in text and "temperature" not in text:
            return ToolResult(success=True, message=self._describe_date_time())

        try:
            latitude, longitude, location_name = self._resolve_location(text)
            weather = self._fetch_current_weather(latitude, longitude)
        except Exception as error:
            return ToolResult(
                success=False,
                message=(
                    "I couldn't reach the weather service right now "
                    f"(check your internet connection). Error: {error}"
                ),
            )

        description = _WEATHER_CODE_DESCRIPTIONS.get(
            weather["weather_code"], "changing conditions"
        )

        message = (
            f"It's currently {weather['temperature_c']:.0f}°C and {description} "
            f"in {location_name}. Feels like {weather['feels_like_c']:.0f}°C."
        )

        return ToolResult(success=True, message=message)

    def _describe_date_time(self) -> str:
        """Answers a plain date/time question using the local system clock.

        Deliberately local-only: the system clock is already an
        authoritative, zero-latency source of truth for "what time/day
        is it", so there's no reason to make a network call for this,
        unlike temperature/conditions which genuinely require live
        data from outside the machine.
        """
        now = datetime.now()
        return (
            f"It's currently {now.strftime('%I:%M %p').lstrip('0')} "
            f"on {now.strftime('%A, %B %d, %Y')}."
        )

    def _resolve_location(self, text: str) -> tuple[float, float, str]:
        """Resolves a location name mentioned in ``text`` to coordinates.

        Falls back to the configured default location if no place
        name can be extracted or geocoding fails, rather than erroring
        out entirely — most requests ("what's the weather?") don't
        name a city at all and mean "here".
        """
        city = self._extract_city(text)

        if not city:
            return self._default_latitude, self._default_longitude, self._default_location_name

        try:
            response = httpx.get(
                _GEOCODING_URL,
                params={"name": city, "count": 1},
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            results = response.json().get("results") or []
        except Exception:
            results = []

        if not results:
            return self._default_latitude, self._default_longitude, self._default_location_name

        match = results[0]
        return match["latitude"], match["longitude"], match.get("name", city)

    @staticmethod
    def _extract_city(text: str) -> str:
        """Pulls a trailing city name out of phrasing like "weather in
        Mumbai" / "mausam kaisa hai Jaipur mein". Best-effort only —
        returns an empty string if nothing recognizable is found,
        which is the common case and just means "use my default
        location"."""
        for marker in (" in ", " mein ", " ke liye "):
            if marker in text:
                return text.split(marker, 1)[-1].strip(" ?.!")
        return ""

    def _fetch_current_weather(self, latitude: float, longitude: float) -> dict:
        response = httpx.get(
            _FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,apparent_temperature,weather_code",
                "timezone": "auto",
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        current = response.json()["current"]

        return {
            "temperature_c": current["temperature_2m"],
            "feels_like_c": current["apparent_temperature"],
            "weather_code": current["weather_code"],
        }
