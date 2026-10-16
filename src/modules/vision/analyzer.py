"""
Vision Analyzer.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.modules.ai.manager import AIManager
from src.modules.vision.config import VisionConfig
from src.modules.vision.models import ScreenCapture

logger = get_logger("Vision.Analyzer")

_DEFAULT_QUESTION = (
    "This is a screenshot taken just now, showing exactly what's on "
    "the screen at this moment. Describe what's currently visible in "
    "a few sentences, based only on what you can actually see in the "
    "image. Identify the application that's in focus from the image "
    "itself, and call out anything that looks important, like error "
    "messages, dialogs, or notifications."
)


class VisionAnalyzer:
    """
    Turns a ``ScreenCapture`` into an answer, using a vision-capable
    Ollama model.
    """

    def __init__(
        self,
        config: VisionConfig | None = None,
        ai: AIManager | None = None,
    ) -> None:
        self.config = config or VisionConfig()
        self._ai = ai or AIManager()

    def analyze(
        self,
        capture: ScreenCapture,
        question: str = "",
    ) -> str:
        """
        Ask the vision model about a screen capture.

        Args:
            capture: The screenshot to analyze.
            question: What to ask about it. Falls back to a general
                "describe the screen" prompt when empty, e.g. for a
                bare "take a screenshot" / "what's on my screen".
        """

        prompt = question.strip() or _DEFAULT_QUESTION

        prompt += (
            " Base your answer strictly on what's actually visible in "
            "the screenshot, not on assumptions."
        )

        # The window title is appended as a soft, explicitly-unverified
        # hint *after* the main instruction, not stated as fact before
        # it. It can be stale or simply wrong — e.g. it reflects
        # whichever window had keyboard focus at the instant the
        # question was asked, which may be the terminal EON is being
        # talked through rather than whatever the user is visually
        # looking at. A small vision model will otherwise anchor hard
        # on a confidently-stated fact and describe that instead of
        # actually reading the image.
        if self.config.include_window_title and capture.window_title:
            prompt += (
                f" (Unverified hint, use only if it matches what you "
                f"see: the foreground window may be titled "
                f"\"{capture.window_title}\". Ignore this hint if it "
                f"doesn't match the image.)"
            )

        try:
            return self._ai.chat_with_image(
                prompt=prompt,
                image_bytes=capture.image_bytes,
                model=self.config.model,
            ).strip()
        except Exception:
            logger.exception(
                "Vision model call failed (model=%s).",
                self.config.model,
            )
            raise
