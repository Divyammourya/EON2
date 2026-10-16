"""
Vision models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ScreenCapture:
    """
    A single screenshot, captured at a point in time.

    Attributes:
        image_bytes: Encoded image data (JPEG), ready to hand to a
            multimodal model or write to disk.
        width: Width in pixels after any downscaling.
        height: Height in pixels after any downscaling.
        window_title: Title of the foreground window at capture time,
            if it could be determined (Windows only, ``None``
            elsewhere or if it couldn't be read).
        captured_at: When the screenshot was taken.
    """

    image_bytes: bytes
    width: int
    height: int
    window_title: str | None = None
    captured_at: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.captured_at is None:
            self.captured_at = datetime.now()


@dataclass(slots=True)
class VisionResult:
    """
    Result of asking the vision model about a screen capture.

    Attributes:
        success: Whether the capture + analysis completed.
        description: The model's answer — a description of the screen,
            or a direct answer to whatever question was asked.
        message: Human-facing status message. Set on failure to
            explain what went wrong (e.g. vision disabled, no display,
            model unreachable); mirrors the ``ActionResult.message``
            pattern used elsewhere in EON.
        window_title: Foreground window title at capture time, if
            known — surfaced here too so callers don't need to keep
            the underlying ``ScreenCapture`` around.
    """

    success: bool
    description: str = ""
    message: str = ""
    window_title: str | None = None
