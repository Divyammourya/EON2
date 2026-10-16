"""Choosing audio-stream settings a device will actually accept.

Why this exists
---------------
EON works in 16 kHz mono 16-bit audio, because that is what Whisper
expects. It used to open the microphone and speaker streams at 16 kHz
regardless of the hardware — and plenty of Windows devices do not support
16 kHz at all, they run at 44.1 or 48 kHz. PortAudio refuses a stream
whose sample rate the device cannot do, so voice failed to start
completely: the microphone never opened and EON could not speak.

The old code even queried each device's real default rate and then
ignored it. These helpers use it: they pick settings the device will
accept, and ``resample_pcm16`` converts between that rate and the 16 kHz
EON works in, so everything downstream is unchanged.

What's here is pure — device probing and audio capture are injected by
the providers, so this is unit tested without any audio hardware.

Requires: Python 3.12+
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

_INPUT_KEY = "max_input_channels"
_OUTPUT_KEY = "max_output_channels"


def choose_stream_settings(
    *,
    wanted_rate: int,
    wanted_channels: int,
    device_default_rate: int,
    supports: Callable[[int, int], bool],
) -> tuple[int, int]:
    """Picks a ``(samplerate, channels)`` pair the device will accept.

    Tries, in order: exactly what was asked for; the wanted rate in mono;
    the device's own default rate; and finally that in mono. The device's
    default rate is always supported by definition, so the third
    candidate is the one that rescues hardware which can't do 16 kHz.

    Channels are relaxed before the rate, because a channel count the
    device can't do is recoverable by dropping to mono, whereas a sample
    rate it can't do is fatal.

    Args:
        wanted_rate: The sample rate EON would prefer.
        wanted_channels: The channel count EON would prefer.
        device_default_rate: The device's own default rate.
        supports: Probes whether the device accepts a pair. The providers
            pass ``sounddevice.check_input_settings`` /
            ``check_output_settings``.

    Returns:
        The first acceptable pair. If none probe as acceptable, the
        wanted settings are returned unchanged so the caller surfaces a
        real error rather than silently doing something else.
    """
    candidates = (
        (wanted_rate, wanted_channels),
        (wanted_rate, 1),
        (device_default_rate, wanted_channels),
        (device_default_rate, 1),
    )

    seen: set[tuple[int, int]] = set()

    for rate, channels in candidates:
        if rate <= 0 or channels <= 0 or (rate, channels) in seen:
            continue
        seen.add((rate, channels))
        try:
            if supports(rate, channels):
                return rate, channels
        except Exception:
            # A probe that itself fails (an unhelpful backend, a device
            # that vanished) must not stop us trying the next candidate.
            continue

    return wanted_rate, wanted_channels


def resolve_device_index(
    requested: str | int | None,
    devices: Sequence[dict[str, Any]],
    kind: str,
) -> int | None:
    """Resolves a configured device to an index, or None for the default.

    Accepts an integer index or a case-insensitive name substring, which
    is what ``sounddevice`` documents — though the providers previously
    passed the value straight to ``int()``, so a name never worked.

    Args:
        requested: An index, a name substring, or None for the default.
        devices: The device list from ``sounddevice.query_devices()``.
        kind: ``"input"`` or ``"output"``.

    Returns:
        The device index, or None if nothing matched (the caller then
        falls back to the platform default).
    """
    if requested is None:
        return None

    if isinstance(requested, int):
        return requested

    text = str(requested).strip()

    if not text:
        return None

    if text.lstrip("-").isdigit():
        return int(text)

    key = _INPUT_KEY if kind == "input" else _OUTPUT_KEY
    needle = text.lower()

    for index, device in enumerate(devices):
        if int(device.get(key, 0) or 0) <= 0:
            continue
        if needle in str(device.get("name", "")).lower():
            return index

    return None


def resample_pcm16(raw: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resamples signed 16-bit mono PCM between two sample rates.

    Linear interpolation. That is not a brick-wall filter, so
    downsampling lets a little high-frequency content fold back — but
    speech energy sits well below the fold point and Whisper is robust
    to it, and this only runs at all when the hardware refused the rate
    EON wanted. Getting recognisable audio out of a 48 kHz microphone is
    worth more than a perfect anti-aliasing filter.

    Args:
        raw: Signed 16-bit little-endian mono PCM.
        from_rate: The sample rate of ``raw``.
        to_rate: The sample rate to produce.

    Returns:
        Resampled PCM, or ``raw`` unchanged when no work is needed.
    """
    if from_rate == to_rate or not raw or from_rate <= 0 or to_rate <= 0:
        return raw

    samples = np.frombuffer(raw, dtype=np.int16)

    if samples.size == 0:
        return raw

    count = int(round(samples.size * to_rate / from_rate))

    if count <= 0:
        return b""

    source_positions = np.arange(samples.size, dtype=np.float64)
    target_positions = np.linspace(0.0, samples.size - 1, count)

    resampled = np.interp(target_positions, source_positions, samples)

    return np.rint(resampled).astype(np.int16).tobytes()
