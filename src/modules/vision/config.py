"""
Vision Config.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VisionConfig:
    """
    Configuration for the Vision module.

    Attributes:
        enabled: Master switch. When ``False``, ``VisionManager`` refuses
            to capture or analyze the screen at all — mirrors
            ``automation_enabled`` for the actions pipeline, but kept
            separate since a user may be happy for EON to open apps
            while still not wanting it looking at their screen (or
            vice versa).
        model: The Ollama vision-capable model to use (e.g.
            ``"llava"``, ``"qwen2.5vl:3b"``, ``"moondream"``). This is
            deliberately separate from the main chat model in
            ``config/models.json`` since most small text models can't
            take image input.
        max_dimension: Screenshots are downscaled so neither side
            exceeds this many pixels before being sent to the model.
            Keeps requests fast and small — vision models don't need
            full native display resolution to read text or describe a
            layout.
        jpeg_quality: Quality used when encoding the screenshot for
            the model. Lower = smaller/faster upload, higher = more
            legible for small on-screen text.
        include_window_title: Whether to prefix the prompt sent to the
            model with the title of the currently focused window, when
            available. Gives the model useful context ("this is VS
            Code" vs. guessing from pixels alone).
    """

    enabled: bool = True
    model: str = "llava"
    max_dimension: int = 1280
    jpeg_quality: int = 80
    include_window_title: bool = True
