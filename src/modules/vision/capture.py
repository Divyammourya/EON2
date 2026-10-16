"""
Screen Capture.
"""

from __future__ import annotations

import io
import os

from src.core.logger import get_logger
from src.modules.vision.config import VisionConfig
from src.modules.vision.models import ScreenCapture

logger = get_logger("Vision.Capture")


class ScreenCapturer:
    """
    Grabs screenshots of the current display, optionally tagged with
    the foreground window's title.

    Uses ``PIL.ImageGrab`` (Windows/macOS) rather than a Linux-capable
    library like ``mss``, matching the rest of EON's tools layer
    (``os.startfile``, ``win32com``), which already assumes a Windows
    desktop.
    """

    def __init__(self, config: VisionConfig | None = None) -> None:
        self.config = config or VisionConfig()

    def capture(self) -> ScreenCapture | None:
        """
        Take a screenshot of the current display.

        Returns ``None`` if no display is available or the underlying
        capture call fails (headless environment, missing Pillow,
        permissions, etc.) rather than raising — callers already have
        a well-defined "vision failed" path via ``VisionResult``.
        """

        try:
            from PIL import ImageGrab
        except ImportError:
            logger.error(
                "Pillow is not installed — run "
                "'pip install Pillow' to enable screen capture."
            )
            return None

        try:
            image = ImageGrab.grab()
        except Exception:
            logger.exception("Failed to grab a screenshot.")
            return None

        image = image.convert("RGB")

        max_dim = self.config.max_dimension

        if max(image.size) > max_dim:
            image.thumbnail((max_dim, max_dim))

        buffer = io.BytesIO()

        image.save(
            buffer,
            format="JPEG",
            quality=self.config.jpeg_quality,
        )

        return ScreenCapture(
            image_bytes=buffer.getvalue(),
            width=image.width,
            height=image.height,
            window_title=self._active_window_title(),
        )

    def _active_window_title(self) -> str | None:
        """
        Best-effort lookup of the foreground window's title.

        Windows-only; returns ``None`` anywhere the ``win32gui``
        extension isn't available or the lookup fails, since a missing
        title is a minor context loss, not a capture failure.

        Also returns ``None`` when the foreground window belongs to
        EON's own process. If EON is run from a plain console, that
        console is the foreground window the instant the user hits
        Enter to ask their question — surfacing its title ("Windows
        PowerShell") to the vision model is worse than useless. Note
        this can't catch the case where EON runs inside an *editor's*
        integrated terminal (the OS-level foreground window there
        belongs to the editor's process, not EON's) — that's why the
        title is always treated as a soft hint in the analyzer prompt,
        never as fact, regardless of this check.
        """

        if not self.config.include_window_title:
            return None

        try:
            import win32gui
            import win32process
        except ImportError:
            return None

        try:
            handle = win32gui.GetForegroundWindow()

            if not handle:
                return None

            try:
                _, pid = win32process.GetWindowThreadProcessId(handle)
                if pid == os.getpid():
                    return None
            except Exception:
                pass

            title = win32gui.GetWindowText(handle)
            return title or None
        except Exception:
            return None
