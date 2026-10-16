"""Unit conversion: exact, offline, and never wrong.

Same reasoning as the calculator — converting 10 km to miles has one right
answer, so the model should never be the one producing it. Ask a 3B model
for a unit conversion and you get a plausible number with no way to tell
it's wrong.

Handles length, mass, volume and time by a factor to a base unit, and
temperature separately (it has offsets, not just factors).

Requires: Python 3.12+
"""

from __future__ import annotations

import re

from src.modules.tools.utility.calculator import format_number

_LENGTH = {
    "mm": 0.001, "millimetre": 0.001, "millimeter": 0.001,
    "cm": 0.01, "centimetre": 0.01, "centimeter": 0.01,
    "m": 1.0, "metre": 1.0, "meter": 1.0,
    "km": 1000.0, "kilometre": 1000.0, "kilometer": 1000.0,
    "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
    "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
    "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
}

_MASS = {
    "mg": 0.001, "milligram": 0.001, "milligrams": 0.001,
    "g": 1.0, "gram": 1.0, "grams": 1.0,
    "kg": 1000.0, "kilogram": 1000.0, "kilograms": 1000.0,
    "lb": 453.59237, "lbs": 453.59237, "pound": 453.59237, "pounds": 453.59237,
    "oz": 28.349523125, "ounce": 28.349523125, "ounces": 28.349523125,
    "tonne": 1000000.0, "tonnes": 1000000.0, "ton": 1000000.0, "tons": 1000000.0,
}

_VOLUME = {
    "ml": 0.001, "millilitre": 0.001, "milliliter": 0.001,
    "l": 1.0, "litre": 1.0, "liter": 1.0, "litres": 1.0, "liters": 1.0,
    "gallon": 3.785411784, "gallons": 3.785411784,
    "pint": 0.473176473, "pints": 0.473176473,
}

_TIME = {
    "second": 1.0, "seconds": 1.0, "sec": 1.0, "secs": 1.0,
    "minute": 60.0, "minutes": 60.0, "min": 60.0, "mins": 60.0,
    "hour": 3600.0, "hours": 3600.0, "hr": 3600.0, "hrs": 3600.0,
    "day": 86400.0, "days": 86400.0,
    "week": 604800.0, "weeks": 604800.0,
}

_FAMILIES = (
    ("length", _LENGTH),
    ("mass", _MASS),
    ("volume", _VOLUME),
    ("time", _TIME),
)

_CELSIUS = {"c", "celsius", "centigrade"}
_FAHRENHEIT = {"f", "fahrenheit"}
_KELVIN = {"k", "kelvin"}

# "<number> <unit> in|to <unit>", e.g. "10 km in miles", "30 c to f".
_CONVERSION = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:degrees?\s+)?(°?\s*[a-zA-Z]{1,15})\s+"
    r"(?:in|to|into|as)\s+"
    r"(?:degrees?\s+)?(°?\s*[a-zA-Z]{1,15})",
    re.I,
)


def _normalise(unit: str) -> str:
    """Lowercases and strips the decoration around a spoken unit."""
    cleaned = unit.lower().replace("°", "").strip()
    cleaned = re.sub(r"^degrees?\s+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.rstrip(".")


def _look_up(unit: str) -> tuple[str, float] | None:
    """Returns ``(family, factor)`` for a unit, or None if unknown."""
    for family, table in _FAMILIES:
        if unit in table:
            return family, table[unit]

    # "kilometres" -> "kilometre", for plurals not listed explicitly.
    if unit.endswith("s"):
        for family, table in _FAMILIES:
            if unit[:-1] in table:
                return family, table[unit[:-1]]

    return None


# Nicer than echoing the user's word back: "86 fahrenheit" reads badly.
_DISPLAY = {
    "c": "°C", "celsius": "°C", "centigrade": "°C",
    "f": "°F", "fahrenheit": "°F",
    "k": "K", "kelvin": "K",
}


def _display(unit: str) -> str:
    """How to print a unit back to the user."""
    return _DISPLAY.get(unit, unit)


def _join(value: float, unit: str) -> str:
    """Joins a number to its unit, tightening degree symbols."""
    number = format_number(value)

    if unit.startswith("°"):
        return f"{number}{unit}"

    return f"{number} {unit}"


def _temperature_scale(unit: str) -> str | None:
    """Returns "c", "f" or "k" for a temperature unit, else None."""
    if unit in _CELSIUS:
        return "c"
    if unit in _FAHRENHEIT:
        return "f"
    if unit in _KELVIN:
        return "k"
    return None


def _to_celsius(value: float, scale: str) -> float:
    if scale == "f":
        return (value - 32.0) * 5.0 / 9.0
    if scale == "k":
        return value - 273.15
    return value


def _from_celsius(value: float, scale: str) -> float:
    if scale == "f":
        return value * 9.0 / 5.0 + 32.0
    if scale == "k":
        return value + 273.15
    return value


def convert(value: float, source: str, target: str) -> float | None:
    """Converts ``value`` between two units, or returns None.

    Returns None when the units belong to different families — converting
    kilograms to kilometres is not a conversion, it's a mistake, and
    guessing at it would be worse than staying quiet.
    """
    source_scale = _temperature_scale(source)
    target_scale = _temperature_scale(target)

    if source_scale and target_scale:
        return _from_celsius(
            _to_celsius(value, source_scale),
            target_scale,
        )

    source_unit = _look_up(source)
    target_unit = _look_up(target)

    if source_unit is None or target_unit is None:
        return None

    if source_unit[0] != target_unit[0]:
        return None

    return value * source_unit[1] / target_unit[1]


def answer(text: str) -> str | None:
    """Answers a unit-conversion question in ``text``, or returns None."""
    match = _CONVERSION.search(text)

    if not match:
        return None

    value = float(match.group(1))
    source = _normalise(match.group(2))
    target = _normalise(match.group(3))

    result = convert(value, source, target)

    if result is None:
        return None

    # Four decimals is plenty for a spoken conversion, and stops
    # "6.213712 miles" being read out digit by digit.
    return (
        f"{_join(value, _display(source))} is "
        f"{_join(round(result, 4), _display(target))}."
    )
