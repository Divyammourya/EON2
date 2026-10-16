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
    assert _feed(detector, 0.5, is_speech=True) is True


def test_does_not_fire_below_minimum():
    detector = BargeInDetector(min_speech_seconds=0.5)
    assert _feed(detector, 0.25, is_speech=True) is False
    assert detector.fired is False


def test_brief_blip_does_not_fire():
    detector = BargeInDetector(min_speech_seconds=0.5)
    # A single short noise burst followed by silence must never fire.
    assert _feed(detector, 0.25, is_speech=True) is False
    assert _feed(detector, 2.0, is_speech=False) is False


def test_gap_resets_the_run():
    detector = BargeInDetector( min_speech_seconds=0.5)
    _feed(detector, 0.25, is_speech=True)
    _feed(detector, 0.5, is_speech=False)  # a pause resets the run
    assert _feed(detector, 0.25, is_speech=True) is False
    # ...but a further continuous stretch still fires.
    assert _feed(detector, 0.5, is_speech=True) is True


def test_fires_only_once():
    detector = BargeInDetector(min_speech_seconds=0.5)
    assert _feed(detector, 0.5, is_speech=True) is True
    assert detector.fired is True
    assert detector.update(FRAME, True) is False
