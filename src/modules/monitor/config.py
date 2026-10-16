"""
Ambient monitor configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class AmbientMonitorConfig:
    """
    Controls background awareness checks.
    """

    enabled: bool = True
    check_interval_seconds: float = 30.0
    downloads_path: Path = field(
        default_factory=lambda: Path.home() / "Downloads",
    )
    calendar_enabled: bool = True
    calendar_warning_minutes: int = 5
    calendar_lookahead_minutes: int = 10
    downloads_enabled: bool = True
    hung_window_enabled: bool = True
    signal_cooldown_minutes: int = 30
