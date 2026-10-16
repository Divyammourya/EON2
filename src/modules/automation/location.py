"""Working out where EON is.

Asks an IP-geolocation service where this machine appears to be, so
that a question like "what's the weather?" means "here" without anyone
having to write their city into a config file — and so that moving
house moves the weather with it.

Design notes:
    - This sends the machine's public IP address to a third party. That
      is the only way to do it without OS-level location services, and
      it is why ``location_auto_detect`` exists as a switch: setting
      ``weather_location_name`` in ``config/settings.json`` to a city
      takes precedence over detection entirely, so a user who would
      rather not phone out never has to.
    - IP geolocation is coarse — city level at best — and a VPN will
      place you wherever the exit node is. It is good enough to answer
      "what's the weather like", not to give directions.
    - Three providers are tried in turn, because a single free endpoint
      having a bad day should not mean EON forgets where it lives.
    - The answer is cached to disk with a time-to-live, so a normal
      launch costs nothing and a move is picked up within
      ``location_cache_hours`` rather than never.

Requires: Python 3.12+, httpx
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from src.core.logger import get_logger

logger = get_logger("Location")

# Tried in order; the first one that answers usefully wins.
_IP_LOOKUP_URLS = (
    "https://ipapi.co/json/",
    "https://ipwho.is/",
    "https://ipinfo.io/json",
)

_REQUEST_TIMEOUT_SECONDS = 6.0

# A descriptive User-Agent. Some of these services reject a browser-like
# one, and an anonymous default gets rate-limited faster.
_USER_AGENT = "EON-Assistant/1.0"

DEFAULT_CACHE_HOURS = 24.0


@dataclass(slots=True)
class Location:
    """A place EON believes it is in, and how it decided.

    Attributes:
        name: Human-readable place name, e.g. "Bangalore".
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
        source: Where this came from — ``"configured"`` (set by the
            user), ``"detected"`` (fresh IP lookup), ``"cached"`` (a
            stored lookup), or ``"fallback"`` (the built-in default,
            used when nothing else worked).
    """

    name: str
    latitude: float
    longitude: float
    source: str = "detected"


def _first_float(payload: dict, *keys: str) -> float | None:
    """Returns the first of ``keys`` that holds a number, or ``None``."""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def parse_location_payload(payload: object) -> tuple[str, float, float] | None:
    """Pulls a place name and coordinates out of a geolocation reply.

    The providers answer with roughly the same information under
    different key names, so this tries the shapes rather than
    committing to one vendor's schema — which also means one of them
    changing a field name doesn't silently break EON's sense of place.

    Args:
        payload: The decoded JSON body.

    Returns:
        ``(name, latitude, longitude)``, or ``None`` if the reply
        doesn't contain a usable place.
    """
    if not isinstance(payload, dict) or payload.get("success") is False:
        return None

    latitude = _first_float(payload, "latitude", "lat")
    longitude = _first_float(payload, "longitude", "lon", "lng")

    if latitude is None or longitude is None:
        # ipinfo.io puts both in one comma-separated string.
        packed = payload.get("loc")
        if isinstance(packed, str) and "," in packed:
            latitude_text, _, longitude_text = packed.partition(",")
            try:
                latitude = float(latitude_text)
                longitude = float(longitude_text)
            except ValueError:
                return None

    if latitude is None or longitude is None:
        return None

    name = str(payload.get("city") or payload.get("region") or "").strip()

    if not name:
        return None

    return name, latitude, longitude


def _http_get(url: str) -> dict:
    """Fetches and decodes a JSON endpoint."""
    response = httpx.get(
        url,
        timeout=_REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": _USER_AGENT},
    )
    response.raise_for_status()
    return response.json()


def detect_location(fetcher: Callable[[str], dict] | None = None) -> Location | None:
    """Asks a geolocation service where this machine appears to be.

    Args:
        fetcher: Fetches a URL and returns decoded JSON. Defaults to
            ``httpx``; injectable so the logic can be tested without a
            network.

    Returns:
        The detected location, or ``None`` if every provider failed.
    """
    get = fetcher or _http_get

    for url in _IP_LOOKUP_URLS:
        try:
            payload = get(url)
        except Exception as error:
            logger.debug("Location lookup via %s failed: %s", url, error)
            continue

        parsed = parse_location_payload(payload)

        if parsed is None:
            continue

        name, latitude, longitude = parsed
        logger.info("Detected location: %s (via %s).", name, url)
        return Location(name=name, latitude=latitude, longitude=longitude)

    logger.warning("Could not work out EON's location from any provider.")
    return None


class LocationResolver:
    """Decides which location EON should use, and remembers it.

    Precedence, highest first:

    1. A place the user configured — their word beats detection, which
       is also what lets them opt out of detection by setting one.
    2. A detection from within the last ``cache_hours``.
    3. A fresh detection.
    4. A stale detection, if the network is down now.
    5. The built-in fallback.

    Attributes:
        _cache_path: Where detections are remembered between runs.
        _cache_hours: How long a detection stays fresh.
        _configured: A user-set location, if any.
        _fallback: Used when nothing else is available.
        _detector: Performs a fresh detection; injectable for tests.
        _memo: The last resolved location, to avoid re-reading the cache
            file (or re-detecting) on every weather question.
        _memo_at: When ``_memo`` was resolved.
    """

    def __init__(
        self,
        *,
        cache_path: str | Path,
        fallback: Location,
        cache_hours: float = DEFAULT_CACHE_HOURS,
        configured: Location | None = None,
        detector: Callable[[], Location | None] | None = None,
    ) -> None:
        self._cache_path = Path(cache_path)
        self._cache_hours = cache_hours
        self._configured = configured
        self._fallback = fallback
        self._detector = detector or detect_location
        self._memo: Location | None = None
        self._memo_at: datetime | None = None

    def resolve(self) -> Location:
        """The location to use right now.

        Never raises: a location EON cannot work out must not be what
        stops it answering a question.
        """
        if self._configured is not None:
            return self._configured

        now = datetime.now()

        if self._memo is not None and self._is_fresh(self._memo_at, now):
            return self._memo

        stored, stored_at = self._read_cache()

        if stored is not None and self._is_fresh(stored_at, now):
            self._remember(stored, now)
            return stored

        detected = self._detect()

        if detected is not None:
            self._write_cache(detected, now)
            self._remember(detected, now)
            return detected

        if stored is not None:
            # Stale, but a real place beats a guessed one.
            self._remember(stored, now)
            return stored

        return self._fallback

    def _is_fresh(self, when: datetime | None, now: datetime) -> bool:
        """Whether something resolved at ``when`` is still usable."""
        if when is None:
            return False
        return now - when < timedelta(hours=self._cache_hours)

    def _remember(self, location: Location, now: datetime) -> None:
        """Memoises a resolution for the rest of this run."""
        self._memo = location
        self._memo_at = now

    def _detect(self) -> Location | None:
        """Runs a fresh detection, converting any failure into ``None``."""
        try:
            return self._detector()
        except Exception as error:
            logger.warning("Location detection raised: %s", error)
            return None

    def _read_cache(self) -> tuple[Location | None, datetime | None]:
        """Reads the stored detection, or ``(None, None)``."""
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None, None

        if not isinstance(data, dict):
            return None, None

        try:
            location = Location(
                name=str(data["name"]),
                latitude=float(data["latitude"]),
                longitude=float(data["longitude"]),
                source="cached",
            )
            detected_at = datetime.fromisoformat(str(data["detected_at"]))
        except (KeyError, TypeError, ValueError):
            return None, None

        return location, detected_at

    def _write_cache(self, location: Location, now: datetime) -> None:
        """Stores a detection so the next launch starts from it."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps(
                    {
                        "name": location.name,
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                        "detected_at": now.isoformat(timespec="seconds"),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            # Worst case EON detects again next launch. Not worth
            # failing a weather answer over.
            logger.warning("Could not write the location cache to %s.", self._cache_path)
