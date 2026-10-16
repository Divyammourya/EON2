"""
Desktop Companion (Hologram) Configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HologramSize(str, Enum):
    """Preset sizes for the hologram overlay window."""

    EXTRA_SMALL = "extra_small" # new 160 diameter
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    FULLSCREEN = "fullscreen"


class HologramTheme(str, Enum):
    """Color themes for the hologram effect."""

    RED_PURPLE = "red_purple"
    GOLDEN = "golden"
    BLUE = "blue"
    CYAN = "cyan"
    PURPLE = "purple"


# Window diameter in pixels for each non-fullscreen size preset.
# FULLSCREEN is resolved against the actual primary screen at runtime
# instead (see HologramOverlay._apply_geometry), since it has to match
# whatever monitor EON is running on rather than a fixed number.
_SIZE_DIAMETERS: dict[HologramSize, int] = {
    HologramSize.EXTRA_SMALL: 160, # new 160 diameter
    HologramSize.SMALL: 240,
    HologramSize.MEDIUM: 380,
    HologramSize.LARGE: 560,
}


@dataclass(slots=True)
class HologramConfig:
    """
    Configuration for the desktop companion hologram overlay.

    Attributes:
        enabled: Master switch. If ``False``, the overlay never opens.
        size: Preset size — small/medium/large sit in the bottom-right
            corner of the primary screen; fullscreen covers it
            entirely.
        theme: Color palette — golden/blue/cyan/purple.
        particles_enabled: Whether floating light particles are drawn.
            Disabling this is the cheapest way to cut CPU/GPU usage
            further, since particles are the only per-object (rather
            than per-frame-constant) animation cost.
        glow_intensity: 0.0-1.0. Controls the strength of the central
            glow and the energy wave's opacity.
        animation_speed: Multiplier applied to every animation's rate
            of change (ring rotation, wave pulse, particle drift).
            1.0 is the default pace; 0.0 effectively freezes the
            animation while still rendering a static hologram.
        transparency: 0.0-1.0 overall window opacity. Applied at the
            window level (compositor-handled) rather than per-element,
            since that's essentially free compared to recomputing
            per-pixel alpha every frame.
        fps: Animation frame rate. 30 is a smooth-looking, low-cost
            default; lower it further to reduce CPU usage on modest
            hardware, especially in fullscreen mode.
    """

    enabled: bool = True
    size: HologramSize = HologramSize.MEDIUM
    theme: HologramTheme = HologramTheme.GOLDEN
    particles_enabled: bool = True
    glow_intensity: float = 0.8
    animation_speed: float = 1.0
    transparency: float = 0.85
    fps: int = 30

    def diameter(self) -> int:
        """Window diameter in pixels for non-fullscreen sizes."""
        return _SIZE_DIAMETERS.get(self.size, _SIZE_DIAMETERS[HologramSize.MEDIUM])

    @staticmethod
    def parse_size(value: object) -> HologramSize:
        """Parses a settings.json / voice-command string into a
        HologramSize, falling back to MEDIUM for anything unrecognized
        rather than raising — a typo in config shouldn't crash
        startup."""
        try:
            return HologramSize(str(value).strip().lower())
        except ValueError:
            return HologramSize.MEDIUM

    @staticmethod
    def parse_theme(value: object) -> HologramTheme:
        """Same idea as parse_size: falls back to GOLDEN rather than
        raising on an unrecognized theme name."""
        try:
            return HologramTheme(str(value).strip().lower())
        except ValueError:
            return HologramTheme.GOLDEN
