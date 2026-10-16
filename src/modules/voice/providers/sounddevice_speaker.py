"""SoundDevice-backed speaker implementation for the EON Voice module.

This module provides ``SoundDeviceSpeaker``, a concrete implementation
of the ``Speaker`` abstraction that plays back audio using the
``sounddevice`` library (a Python binding for PortAudio).

Design notes:
    - ``SoundDeviceSpeaker`` is the only place in this module that
      imports ``sounddevice``. All other Voice components depend
      solely on the ``Speaker`` abstraction, keeping the concrete
      audio library isolated behind a single implementation
      (Dependency Inversion Principle), mirroring
      ``SoundDeviceMicrophone``.
    - Playback is performed synchronously via ``sd.OutputStream.write``,
      called on small (~50ms) chunks in a loop rather than one write
      for the whole clip. ``stop()``/``flush()`` set a flag checked
      between chunks rather than calling PortAudio's ``abort()``/
      ``start()`` from another thread — cross-thread stream control
      calls raced with an in-progress ``write()`` in practice and could
      leave the stream producing no audio on subsequent calls, so every
      PortAudio call now stays on the single thread that owns ``play()``.
    - All failures raised by ``sounddevice`` or PortAudio are
      translated into ``SpeakerError`` at the boundary of this class,
      so callers never need to catch library-specific exception types.

Requires: Python 3.12+, sounddevice, numpy
"""

from __future__ import annotations

import threading
from typing import Any

import numpy as np
import sounddevice as sd

from src.core.logger import get_logger
from src.modules.voice.exceptions import SpeakerError
from src.modules.voice.speaker import Speaker, SpeakerDeviceInfo
from src.modules.voice.stream_settings import (
    choose_stream_settings,
    resample_pcm16,
    resolve_device_index,
)

logger = get_logger("Speaker")

_DEFAULT_DTYPE = "int16"


def _probe_output(device: int, rate: int, channels: int) -> bool:
    """Whether PortAudio will accept this output configuration."""
    try:
        sd.check_output_settings(
            device=device,
            samplerate=rate,
            channels=channels,
            dtype=_DEFAULT_DTYPE,
        )
        return True
    except Exception:
        return False


class SoundDeviceSpeaker(Speaker):
    """Speaker implementation backed by the ``sounddevice`` library.

    ``SoundDeviceSpeaker`` plays raw, signed 16-bit PCM audio through a
    ``sounddevice.OutputStream``. It performs no decoding of container
    formats (e.g. WAV headers); callers are responsible for supplying
    raw PCM frames matching the device's configured sample rate and
    channel count.

    Attributes:
        _device_info: Metadata describing the resolved output device.
        _sample_rate_hz: Sample rate, in hertz, audio is played back at.
        _channels: Number of audio channels played back.
        _stream: The underlying ``sounddevice.OutputStream``, or
            ``None`` if the device has not been opened.
        _is_open: Whether the device is currently open.
        _is_playing: Whether playback is currently in progress.
        _playback_lock: Serializes concurrent calls to ``play``.
    """

    def __init__(
        self,
        device_id: str | int | None = None,
        sample_rate_hz: int = 16_000,
        channels: int = 1,
    ) -> None:
        """Resolves and describes the output device to be used.

        Args:
            device_id: Identifier of the output device to use, as
                accepted by ``sounddevice`` (an integer index or a
                device name substring). If ``None``, the platform's
                default output device is used.
            sample_rate_hz: Sample rate, in hertz, to play audio back
                at.
            channels: Number of audio channels to play back.

        Raises:
            ValueError: If ``sample_rate_hz`` or ``channels`` is not
                greater than zero.
            SpeakerError: If the requested device cannot be resolved
                or queried.
        """
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be greater than zero.")

        if channels <= 0:
            raise ValueError("channels must be greater than zero.")

        try:
            default_output_id = sd.default.device[1]
            resolved_id = resolve_device_index(
                device_id,
                sd.query_devices(),
                "output",
            )
            if resolved_id is None:
                resolved_id = default_output_id
            device_query: dict[str, Any] = sd.query_devices(resolved_id, "output")
        except Exception as exc:
            raise SpeakerError(
                "Failed to resolve or query the requested output device.",
                details={"device_id": device_id, "reason": str(exc)},
            ) from exc

        device_default_rate = int(device_query["default_samplerate"])

        self._device_info = SpeakerDeviceInfo(
            device_id=str(resolved_id),
            name=str(device_query["name"]),
            sample_rate_hz=device_default_rate,
            channels=int(device_query["max_output_channels"]),
            is_default=(resolved_id == default_output_id),
        )

        self._sample_rate_hz = sample_rate_hz
        self._channels = channels

        # The device may not accept the 16 kHz EON works in. Pick
        # settings it will accept, then resample in play() so callers
        # can keep handing us 16 kHz mono.
        self._stream_rate_hz, self._stream_channels = choose_stream_settings(
            wanted_rate=sample_rate_hz,
            wanted_channels=channels,
            device_default_rate=device_default_rate,
            supports=lambda rate, count: _probe_output(
                resolved_id,
                rate,
                count,
            ),
        )

        if self._stream_rate_hz != sample_rate_hz:
            logger.info(
                "Speaker '%s' does not support %s Hz; playing at %s Hz "
                "and resampling.",
                self._device_info.name,
                sample_rate_hz,
                self._stream_rate_hz,
            )

        self._stream: sd.OutputStream | None = None
        self._is_open = False
        self._is_playing = False
        self._playback_lock = threading.Lock()
        # Playback is written in small chunks (see play()) and this flag
        # is checked between chunks to stop early. This is deliberately
        # NOT done via stream.abort()/start() called from another
        # thread: PortAudio's start/stop/abort calls are not safe to
        # interleave with an in-progress write() from a different
        # thread, and doing so was observed to leave the stream in a
        # state where later writes silently produced no audio. Using a
        # flag keeps every stream operation on the single thread that
        # owns play(), which is safe.
        self._stop_requested = threading.Event()

        # Small enough that a stop request is noticed almost
        # instantly, large enough to keep per-chunk overhead low.
        self._chunk_frames = max(1, int(self._stream_rate_hz * 0.05))  # ~50ms

    @property
    def device_info(self) -> SpeakerDeviceInfo:
        """Returns metadata describing this speaker device."""
        return self._device_info

    @property
    def is_open(self) -> bool:
        """Whether the speaker device is currently open."""
        return self._is_open

    @property
    def is_playing(self) -> bool:
        """Whether the speaker is currently outputting audio."""
        return self._is_playing

    def open(self) -> None:
        """Opens the speaker device and prepares it for playback.

        Raises:
            SpeakerError: If the device is already open, or the output
                stream cannot be created or opened.
        """
        if self._is_open:
            raise SpeakerError(
                "Cannot open a speaker device that is already open.",
                details={"device_id": self._device_info.device_id},
            )
        try:
            self._stream = sd.OutputStream(
                device=int(self._device_info.device_id),
                samplerate=self._stream_rate_hz,
                channels=self._stream_channels,
                dtype=_DEFAULT_DTYPE,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise SpeakerError(
                "Failed to create the output stream for the speaker device.",
                details={
                    "device_id": self._device_info.device_id,
                    "device_name": self._device_info.name,
                    "samplerate": self._stream_rate_hz,
                    "channels": self._stream_channels,
                    "reason": str(exc),
                },
            ) from exc
        self._is_open = True

    def close(self) -> None:
        """Closes the speaker device and releases its resources.

        Raises:
            SpeakerError: If the device is not open, or the stream
                fails to close cleanly.
        """
        if not self._is_open or self._stream is None:
            raise SpeakerError(
                "Cannot close a speaker device that is not open.",
                details={"device_id": self._device_info.device_id},
            )
        if self._is_playing:
            self.stop()
        try:
            self._stream.close()
        except Exception as exc:
            raise SpeakerError(
                "Failed to close the speaker output stream.",
                details={"device_id": self._device_info.device_id},
            ) from exc
        finally:
            self._stream = None
            self._is_open = False

    def play(self, audio: bytes) -> None:
        """Plays raw PCM audio data through the speaker device.

        Blocks until the supplied audio has been written to the
        device, or until another thread calls ``stop()`` — audio is
        written in small chunks specifically so a stop request can be
        noticed and acted on within roughly one chunk's duration
        instead of only after the entire clip has been written.

        Args:
            audio: Raw, signed 16-bit PCM audio data matching this
                device's configured sample rate and channel count.

        Raises:
            SpeakerError: If the device is not open, or the audio
                cannot be played.
        """
        if not self._is_open or self._stream is None:
            raise SpeakerError(
                "Cannot play audio on a speaker device that is not open.",
                details={"device_id": self._device_info.device_id},
            )
        with self._playback_lock:
            self._is_playing = True
            self._stop_requested.clear()
            try:
                samples = self._prepare_for_stream(audio)
                total_frames = samples.shape[0]
                offset = 0
                while offset < total_frames:
                    if self._stop_requested.is_set():
                        break
                    end = min(offset + self._chunk_frames, total_frames)
                    self._stream.write(samples[offset:end])
                    offset = end
            except Exception as exc:
                raise SpeakerError(
                    "Failed to play audio through the speaker device.",
                    details={"device_id": self._device_info.device_id},
                ) from exc
            finally:
                self._is_playing = False
                self._stop_requested.clear()

    def _prepare_for_stream(self, audio: bytes) -> np.ndarray:
        """Converts caller audio into the stream's format.

        Callers hand us mono PCM at ``self._sample_rate_hz``. The stream
        may have been opened at a different rate or channel count
        because the device refused what EON asked for, so the audio is
        resampled and channel-mapped to match before it is written.
        """
        if self._stream_rate_hz != self._sample_rate_hz:
            audio = resample_pcm16(
                audio,
                self._sample_rate_hz,
                self._stream_rate_hz,
            )

        samples = np.frombuffer(audio, dtype=np.int16).reshape(-1, self._channels)

        if self._stream_channels == self._channels:
            return samples

        if self._channels == 1:
            return np.repeat(samples, self._stream_channels, axis=1)

        if self._channels > self._stream_channels:
            return samples[:, : self._stream_channels]

        # Fewer source channels than the device wants: repeat to fill.
        repeats = -(-self._stream_channels // self._channels)
        return np.tile(samples, (1, repeats))[:, : self._stream_channels]

    def stop(self) -> None:
        """Stops any audio currently being played through the device.

        Signals the in-progress ``play()`` call (if any, potentially
        running on another thread) to stop writing further chunks.
        This does not call into PortAudio itself, since doing so from
        a thread other than the one actively writing to the stream is
        not safe and can leave the stream unable to produce audio on
        later calls. As a result there is a small tail (at most one
        chunk, ~50ms) of already-buffered audio that finishes playing
        out; this is intentional and keeps the stream in a reliably
        good state for the next ``play()`` call.

        Raises:
            SpeakerError: If the device is not open.
        """
        if not self._is_open or self._stream is None:
            raise SpeakerError(
                "Cannot stop a speaker device that is not open.",
                details={"device_id": self._device_info.device_id},
            )
        self._stop_requested.set()
        self._is_playing = False

    def flush(self) -> None:
        """Discards any buffered, not-yet-played audio data.

        Raises:
            SpeakerError: If the device's buffered audio cannot be
                flushed.
        """
        self.stop()

    @classmethod
    def enumerate_devices(cls) -> list[SpeakerDeviceInfo]:
        """Lists the output devices available on the current platform.

        Returns:
            Metadata for every audio device reporting at least one
            output channel.

        Raises:
            SpeakerError: If available devices cannot be enumerated.
        """
        try:
            devices: list[dict[str, Any]] = sd.query_devices()
            default_output_id = sd.default.device[1]
        except Exception as exc:
            raise SpeakerError("Failed to enumerate output devices.") from exc

        return [
            SpeakerDeviceInfo(
                device_id=str(index),
                name=str(device["name"]),
                sample_rate_hz=int(device["default_samplerate"]),
                channels=int(device["max_output_channels"]),
                is_default=(index == default_output_id),
            )
            for index, device in enumerate(devices)
            if device.get("max_output_channels", 0) > 0
        ]
