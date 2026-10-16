"""Tests for the barge-in detector (speech-triggered interruption).

Pure logic, no audio or microphone needed. Frames are 0.25s because
0.25 is exactly representable in binary floating point, so the run
lengths accumulate with no rounding drift.
"""

from __future__ import annotations

from src.modules.voice.bargein import BargeInDetector

FRAME = 0.25


def _feed(detector: BargeInDetector, seconds: float, is_speech: bool) -> bool:
    """Feeds ``seconds`` of identical frames; True if any frame fired."""
    fired = False
    for _ in range(round(seconds / FRAME)):
        if detector.update(FRAME, is_speech):
            fired = True
    return fired


def test_fires_after_sustained_speech():
    detector = BargeInDetector(min_speech_seconds=0.5)
    assert _feed(detector, 0.5, is_speech=True) Is True

