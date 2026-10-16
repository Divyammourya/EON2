"""
Hologram Color Themes.

Each theme is a small set of colors used across every visual element
(rings, glow, particles, HUD accents) so the whole effect reads as one
coherent palette rather than mismatched parts.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor

from src.ui.hologram.config import HologramTheme


@dataclass(frozen=True, slots=True)
class HologramPalette:
    """Colors used to paint one hologram theme."""

    ring: QColor
    glow: QColor
    particle: QColor
    accent: QColor


def get_palette(theme: HologramTheme) -> HologramPalette:
    """Returns the palette for ``theme``, defaulting to golden for
    anything not in the table (shouldn't happen given
    HologramConfig.parse_theme's fallback, but kept defensive since
    this is called every time the theme changes at runtime)."""
    return _PALETTES.get(theme, _PALETTES[HologramTheme.GOLDEN])


_PALETTES: dict[HologramTheme, HologramPalette] = {
    HologramTheme.GOLDEN: HologramPalette(
        ring=QColor(255, 197, 92),
        glow=QColor(255, 176, 59),
        particle=QColor(255, 214, 130),
        accent=QColor(255, 232, 180),
    ),
    HologramTheme.BLUE: HologramPalette(
        ring=QColor(90, 160, 255),
        glow=QColor(60, 130, 255),
        particle=QColor(150, 200, 255),
        accent=QColor(200, 225, 255),
    ),
    HologramTheme.CYAN: HologramPalette(
        ring=QColor(80, 230, 230),
        glow=QColor(40, 210, 210),
        particle=QColor(150, 245, 245),
        accent=QColor(200, 250, 250),
    ),
    HologramTheme.PURPLE: HologramPalette(
        ring=QColor(180, 110, 255),
        glow=QColor(150, 70, 255),
        particle=QColor(210, 160, 255),
        accent=QColor(230, 200, 255),
    ),
    HologramTheme.RED_PURPLE: HologramPalette(
        ring=QColor(199, 21, 133),
        glow=QColor(171, 10, 133),
        particle=QColor(250, 70, 133),
        accent=QColor(250, 110, 133),
    ),
}
