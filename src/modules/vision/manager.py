"""
Vision Manager.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.modules.vision.analyzer import VisionAnalyzer
from src.modules.vision.capture import ScreenCapturer
from src.modules.vision.config import VisionConfig
from src.modules.vision.models import VisionResult

logger = get_logger("Vision")


class VisionManager:
    """
    Facade for EON's screen vision: "what's on my screen", "what does
    this error say", "describe this window", etc.

    Mirrors the shape of the other module managers (``PerceptionManager``,
    ``RecallManager``) — a small facade over the module's internals so
    callers (the action executor, later maybe the proactive loop) don't
    need to know about ``ScreenCapturer``/``VisionAnalyzer`` directly.
    """

    def __init__(
        self,
        config: VisionConfig | None = None,
        capturer: ScreenCapturer | None = None,
        analyzer: VisionAnalyzer | None = None,
    ) -> None:
        self.config = config or VisionConfig()
        self._capturer = capturer or ScreenCapturer(self.config)
        self._analyzer = analyzer or VisionAnalyzer(self.config)

    def describe_screen(self, question: str = "") -> VisionResult:
        """
        Capture the screen and answer a question about it (or give a
        general description if no question is given).
        """

        if not self.config.enabled:
            return VisionResult(
                success=False,
                message=(
                    "Screen vision is currently disabled, sir. Enable "
                    "'vision_enabled' in config/settings.json if you'd "
                    "like me to look at your screen."
                ),
            )

        capture = self._capturer.capture()

        if capture is None:
            return VisionResult(
                success=False,
                message=(
                    "I wasn't able to capture the screen. Make sure "
                    "Pillow is installed and a display is available."
                ),
            )

        try:
            description = self._analyzer.analyze(capture, question)
        except Exception:
            return VisionResult(
                success=False,
                message=(
                    f"I captured the screen but the vision model "
                    f"('{self.config.model}') didn't respond. Make sure "
                    f"it's pulled in Ollama (`ollama pull "
                    f"{self.config.model}`) and Ollama is running."
                ),
                window_title=capture.window_title,
            )

        return VisionResult(
            success=True,
            description=description,
            window_title=capture.window_title,
        )
