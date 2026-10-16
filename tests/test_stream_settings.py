"""Tests for audio stream settings: device choice and resampling.

Pure logic only — the providers import ``sounddevice``, which has no
audio backend here, so nothing in this file touches them. That is the
point of keeping these helpers separate.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.modules.voice.stream_settings import (
    choose_stream_settings,
    ensure_stream_started,
    resample_pcm16,
    resolve_device_index,
)


def _supports_only(allowed: set[tuple[int, int]]):
    """A fake probe that accepts only the listed pairs."""
    return lambda rate, channels: (rate, channels) in allowed


# --- choosing stream settings ------------------------------------------


def test_prefers_what_was_asked_for():
    rate, channels = choose_stream_settings(
        wanted_rate=16_000,
        wanted_channels=1,
        device_default_rate=48_000,
        supports=_supports_only({(16_000, 1)}),
    )

    assert (rate, channels) == (16_000, 1)


def test_falls_back_to_the_device_default_rate():
    # The real-world case: a Windows device that cannot do 16 kHz at all.
    rate, channels = choose_stream_settings(
        wanted_rate=16_000,
        wanted_channels=1,
        device_default_rate=48_000,
        supports=_supports_only({(48_000, 1)}),
    )

    assert (rate, channels) == (48_000, 1)


def test_relaxes_channels_before_the_rate():
    rate, channels = choose_stream_settings(
        wanted_rate=16_000,
        wanted_channels=2,
        device_default_rate=48_000,
        supports=_supports_only({(16_000, 1)}),
    )

    assert (rate, channels) == (16_000, 1)


def test_a_failing_probe_does_not_stop_the_search():
    calls: list[tuple[int, int]] = []

    def flaky(rate: int, channels: int) -> bool:
        calls.append((rate, channels))
        if rate == 16_000:
            raise RuntimeError("backend unhappy")
        return True

    rate, channels = choose_stream_settings(
        wanted_rate=16_000,
        wanted_channels=1,
        device_default_rate=48_000,
        supports=flaky,
    )

    assert (rate, channels) == (48_000, 1)
    assert (16_000, 1) in calls


def test_falls_back_to_the_wanted_settings_when_nothing_probes_well():
    # So the caller fails with a real PortAudio error rather than
    # silently using something the user didn't ask for.
    rate, channels = choose_stream_settings(
        wanted_rate=16_000,
        wanted_channels=1,
        device_default_rate=48_000,
        supports=_supports_only(set()),
    )

    assert (rate, channels) == (16_000, 1)


# --- resolving a configured device -------------------------------------


_DEVICES = [
    {"name": "Microsoft Sound Mapper - Input", "max_input_channels": 2,
     "max_output_channels": 0},
    {"name": "Microphone (Realtek Audio)", "max_input_channels": 2,
     "max_output_channels": 0},
    {"name": "Speakers (Realtek Audio)", "max_input_channels": 0,
     "max_output_channels": 2},
]


def test_none_means_the_default():
    assert resolve_device_index(None, _DEVICES, "input") is None


def test_an_integer_index_is_used_as_is():
    assert resolve_device_index(2, _DEVICES, "output") == 2


def test_a_numeric_string_is_parsed():
    assert resolve_device_index("1", _DEVICES, "input") == 1


def test_a_name_substring_is_resolved():
    assert resolve_device_index("realtek", _DEVICES, "input") == 1
    assert resolve_device_index("Speakers", _DEVICES, "output") == 2


def test_the_kind_is_respected():
    # "Speakers" has no input channels, so it is not a valid input.
    assert resolve_device_index("Speakers", _DEVICES, "input") is None


def test_an_unknown_name_falls_back_to_the_default():
    assert resolve_device_index("nonexistent", _DEVICES, "input") is None


def test_empty_string_means_the_default():
    assert resolve_device_index("   ", _DEVICES, "input") is None


# --- resampling --------------------------------------------------------


def test_resampling_is_a_no_op_at_the_same_rate():
    raw = b"\x01\x00\x02\x00"

    assert resample_pcm16(raw, 16_000, 16_000) == raw


def test_resampling_handles_empty_input():
    assert resample_pcm16(b"", 48_000, 16_000) == b""


def test_downsampling_scales_the_sample_count():
    samples = np.zeros(48_000, dtype=np.int16)

    out = resample_pcm16(samples.tobytes(), 48_000, 16_000)

    assert len(np.frombuffer(out, dtype=np.int16)) == 16_000


def test_upsampling_scales_the_sample_count():
    samples = np.zeros(16_000, dtype=np.int16)

    out = resample_pcm16(samples.tobytes(), 16_000, 48_000)

    assert len(np.frombuffer(out, dtype=np.int16)) == 48_000


def test_resampling_preserves_a_tone():
    # The real question isn't the sample count, it's whether the audio
    # still sounds like the same thing afterwards.
    rate = 48_000
    seconds = 0.1
    time = np.arange(int(rate * seconds)) / rate
    tone = (np.sin(2 * np.pi * 440 * time) * 10_000).astype(np.int16)

    out = resample_pcm16(tone.tobytes(), 48_000, 16_000)
    samples = np.frombuffer(out, dtype=np.int16)

    windowed = samples * np.hanning(len(samples))
    spectrum = np.abs(np.fft.rfft(windowed))
    frequencies = np.fft.rfftfreq(len(samples), 1 / 16_000)

    dominant = frequencies[int(np.argmax(spectrum))]

    assert dominant == pytest.approx(440, abs=10)


# --- starting a stream that may already be running ---------------------


class _Stream:
    """A minimal stand-in for a sounddevice stream."""

    def __init__(self, *, active: bool = False, fail_start: int = 0) -> None:
        self.active = active
        self._fail_start = fail_start
        self.starts = 0
        self.stops = 0

    def start(self) -> None:
        self.starts += 1
        if self.starts <= self._fail_start:
            raise RuntimeError(f"start refused (#{self.starts})")
        self.active = True

    def stop(self) -> None:
        self.stops += 1
        self.active = False


def _start(stream: _Stream) -> str | None:
    return ensure_stream_started(
        is_active=lambda: stream.active,
        start=stream.start,
        stop=stream.stop,
    )


def test_starting_an_idle_stream_succeeds():
    stream = _Stream()

    assert _start(stream) is None
    assert stream.active is True
    assert stream.starts == 1


def test_an_already_running_stream_is_adopted():
    # The stale state left behind by a listener stopped mid-window: the
    # stream is running, so that is the state we wanted all along, and
    # calling start() on it would have raised.
    stream = _Stream(active=True)

    assert _start(stream) is None
    assert stream.starts == 0


def test_a_refused_start_is_retried():
    stream = _Stream(fail_start=1)

    assert _start(stream) is None
    assert stream.active is True
    assert stream.starts == 2


def test_a_half_started_stream_is_forced_back_into_a_known_state():
    class HalfStarted(_Stream):
        def start(self) -> None:
            self.starts += 1
            if self.starts == 1:
                # Left running despite reporting an error.
                self.active = True
                raise RuntimeError("start refused")
            self.active = True

    stream = HalfStarted()

    assert _start(stream) is None
    assert stream.active is True
    assert stream.stops == 1


def test_a_stream_that_will_not_start_reports_why():
    stream = _Stream(fail_start=99)

    failure = _start(stream)

    assert failure is not None
    assert "start refused" in failure
    assert stream.active is False
