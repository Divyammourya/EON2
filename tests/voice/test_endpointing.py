"""Tests for the utterance endpointing state machine.

Pure logic, no audio or microphone needed.

Frames are 0.25s because 0.25 is exactly representable in binary
floating point, so durations like 0.75 and 1.0 accumulate with no
rounding drift. (Real audio frames are arbitrary-length floats; the
thresholds are reached within a frame, which is all the state machine
needs.)
"""

from __future__ import annotations

from src.modules.voice.endpointing import (
    EndpointDecision,
    UtteranceEndpoint,
)

FRAME = 0.25


def _feed(endpoint: UtteranceEndpoint, seconds: float, is_speech: bool):
    """Feeds ``seconds`` worth of identical frames, returning the last decision."""
    decision = EndpointDecision.CONTINUE
    for _ in range(round(seconds / FRAME)):
        decision = endpoint.update(FRAME, is_speech)
        if decision is not EndpointDecision.CONTINUE:
            return decision
    return decision


def _endpoint(**overrides) -> UtteranceEndpoint:
    defaults = dict(
        silence_end_seconds=0.75,
        max_seconds=15.0,
        min_speech_seconds=0.5,
        start_timeout_seconds=1.0,
    )
    defaults.update(overrides)
    return UtteranceEndpoint(**defaults)


def test_silence_only_stops_as_no_speech():
    endpoint = _endpoint(start_timeout_seconds=1.0)
    assert _feed(endpoint, 1.0, is_speech=False) is EndpointDecision.STOP_NO_SPEECH


def test_speech_then_silence_ends_the_utterance():
    endpoint = _endpoint()
    assert _feed(endpoint, 1.0, is_speech=True) is EndpointDecision.CONTINUE
    assert _feed(endpoint, 0.75, is_speech=False) is EndpointDecision.STOP_SPEECH_ENDED


def test_speaking_continuously_does_not_end_early():
    endpoint = _endpoint()
    assert _feed(endpoint, 2.0, is_speech=True) is EndpointDecision.CONTINUE


def test_hard_cap_stops_long_speech():
    endpoint = _endpoint(max_seconds=1.0)
    assert _feed(endpoint, 1.0, is_speech=True) is EndpointDecision.STOP_MAX_DURATION


def test_brief_blip_below_min_speech_is_not_an_utterance():
    endpoint = _endpoint(min_speech_seconds=0.5)
    assert _feed(endpoint, 0.25, is_speech=True) is EndpointDecision.CONTINUE
    assert _feed(endpoint, 0.75, is_speech=False) is EndpointDecision.STOP_NO_SPEECH


def test_pause_shorter_than_silence_end_keeps_recording():
    endpoint = _endpoint(silence_end_seconds=0.75)
    _feed(endpoint, 0.5, is_speech=True)
    # A brief 0.5s gap mid-sentence must not end the utterance.
    assert _feed(endpoint, 0.5, is_speech=False) is EndpointDecision.CONTINUE
    assert endpoint.speech_started is True
