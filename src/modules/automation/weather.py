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

from dataclasses import dataclass
from datetime import datetime

import httpx

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
_REQUEST_TIMEOUT_SECONDS = 6.0

# Weather codes that mean something is falling out of the sky.
_WET_WEATHER_CODES = frozenset(
    {51, 53, 55, 61, 63, 65, 71, 73, 75, 80, 81, 82, 95, 96, 99}
)

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


def describe_air_quality(index: float) -> str:
    """Turns an air quality index into a plain-language band.

    Uses the US EPA bands, which run 0-500 and are close enough to the
    CPCB scale used in India to be recognisable. Deliberately vague
    about the number itself: "unhealthy" tells the user what to do with
    their morning, "187" mostly doesn't.

    Args:
        index: The air quality index.

    Returns:
        A short description of the band the index falls in.
    """
    if index <= 50:
        return "good"
    if index <= 100:
        return "moderate"
    if index <= 150:
        return "unhealthy for sensitive groups"
    if index <= 200:
        return "unhealthy"
    if index <= 300:
        return "very unhealthy"
    return "hazardous"


@dataclass(slots=True)
class WeatherReadings:
    """One set of current conditions for one place.

    Structured rather than pre-formatted, so the weather tool's own
    answer and the morning briefing can phrase the same numbers
    differently without either re-fetching them.

    Attributes:
        location_name: Human-readable name of the place.
        temperature_c: Air temperature, in degrees Celsius.
        feels_like_c: Apparent temperature, in degrees Celsius.
        humidity_percent: Relative humidity, if the API returned it.
        wind_kph: Wind speed in km/h, if the API returned it.
        weather_code: WMO weather code describing the conditions.
        air_quality_index: Air quality index, if it could be fetched.
        pm2_5: Fine particulate concentration, if available.
    """

    location_name: str
    temperature_c: float
    feels_like_c: float
    humidity_percent: float | None
    wind_kph: float | None
    weather_code: int
    air_quality_index: float | None = None
    pm2_5: float | None = None

    @property
    def description(self) -> str:
        """Plain-language description of the current conditions."""
        return _WEATHER_CODE_DESCRIPTIONS.get(
            self.weather_code, "changing conditions"
        )

    @property
    def is_wet(self) -> bool:
        """Whether the conditions involve precipitation."""
        return self.weather_code in _WET_WEATHER_CODES

    @property
    def air_quality_description(self) -> str | None:
        """Plain-language band for the air quality, or ``None``."""
        if self.air_quality_index is None:
            return None
        return describe_air_quality(self.air_quality_index)


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
            readings = self.current_readings(text)
        except Exception as error:
            return ToolResult(
                success=False,
                message=(
                    "I couldn't reach the weather service right now "
                    f"(check your internet connection). Error: {error}"
                ),
            )

        message = (
            f"It's currently {readings.temperature_c:.0f}°C and "
            f"{readings.description} in {readings.location_name}. "
            f"Feels like {readings.feels_like_c:.0f}°C."
        )

        if readings.humidity_percent is not None:
            message += f" Humidity is {readings.humidity_percent:.0f}%."

        if readings.air_quality_description is not None:
            message += f" Air quality is {readings.air_quality_description}."

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

    def current_readings(self, location_text: str = "") -> WeatherReadings:
        """Fetches the current conditions for a location.

        This is the structured entry point — used by ``execute`` and by
        the morning briefing alike. Air quality comes from a separate
        Open-Meteo endpoint and is treated as a bonus: if it fails, the
        temperature and conditions are still returned rather than the
        whole reading being lost.

        Args:
            location_text: Text that may name a city, or "" for the
                configured default location.

        Returns:
            The current conditions.

        Raises:
            Exception: If the location cannot be resolved or the weather
                service cannot be reached. Callers surface this to the
                user, since it usually means the network is down.
        """
        latitude, longitude, location_name = self._resolve_location(location_text)
        weather = self._fetch_current_weather(latitude, longitude)
        air_quality_index, pm2_5 = self._fetch_air_quality(latitude, longitude)

        return WeatherReadings(
            location_name=location_name,
            temperature_c=weather["temperature_c"],
            feels_like_c=weather["feels_like_c"],
            humidity_percent=weather["humidity_percent"],
            wind_kph=weather["wind_kph"],
            weather_code=weather["weather_code"],
            air_quality_index=air_quality_index,
            pm2_5=pm2_5,
        )

    def _fetch_air_quality(
        self, latitude: float, longitude: float
    ) -> tuple[float | None, float | None]:
        """Fetches the air quality index and PM2.5, or (None, None).

        Best-effort on purpose: air quality is a second network call to
        a second host, and a useful answer about the weather should not
        be lost because the air quality service is having a bad day.
        """
        try:
            response = httpx.get(
                _AIR_QUALITY_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "us_aqi,pm2_5",
                    "timezone": "auto",
                },
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            current = response.json()["current"]
            return current.get("us_aqi"), current.get("pm2_5")
        except Exception:
            return None, None

    def _fetch_current_weather(self, latitude: float, longitude: float) -> dict:
        response = httpx.get(
            _FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,apparent_temperature,"
                    "relative_humidity_2m,wind_speed_10m,weather_code"
                ),
                "timezone": "auto",
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        current = response.json()["current"]

        return {
            "temperature_c": current["temperature_2m"],
            "feels_like_c": current["apparent_temperature"],
            "humidity_percent": current.get("relative_humidity_2m"),
            "wind_kph": current.get("wind_speed_10m"),
            "weather_code": current["weather_code"],
        }
