"""SoundDevice-backed microphone implementation for the EON Voice module.

This module provides ``SoundDeviceMicrophone``, a concrete
implementation of the ``Microphone`` abstraction that captures audio
using the ``sounddevice`` library (a Python binding for PortAudio).

Design notes:
    - ``SoundDeviceMicrophone`` is the only place in the Voice module
      that imports ``sounddevice``. All other Voice components depend
      solely on the ``Microphone`` abstraction, keeping the concrete
      audio library isolated behind a single implementation
      (Dependency Inversion Principle).
    - Captured audio blocks are delivered asynchronously by
      ``sounddevice`` via a callback; this implementation buffers them
      in a thread-safe queue so ``read_frame`` can expose a simple,
      synchronous pull-based interface to callers (Single
      Responsibility Principle: callback plumbing is fully encapsulated
      and never leaks into the public interface).
    - All failures raised by ``sounddevice`` or PortAudio are translated
      into ``MicrophoneError`` at the boundary of this class, so
      callers never need to catch library-specific exception types.

Requires: Python 3.12+, sounddevice
"""

from __future__ import annotations

import queue
from typing import Any

import sounddevice as sd

from src.modules.voice.exceptions import MicrophoneError
from src.modules.voice.microphone import Microphone, MicrophoneDeviceInfo

_DEFAULT_READ_TIMEOUT_SECONDS = 5.0
_DEFAULT_DTYPE = "int16"
_DEFAULT_AUDIO_QUEUE_SIZE = 50


class SoundDeviceMicrophone(Microphone):
    """Microphone implementation backed by the ``sounddevice`` library.

    ``SoundDeviceMicrophone`` captures audio using a ``sounddevice``
    ``InputStream``. Audio blocks are produced asynchronously by the
    underlying PortAudio callback thread and buffered in an internal
    queue, allowing ``read_frame`` to synchronously return one captured
    block of audio at a time.

    Attributes:
        _device_info: Metadata describing the resolved input device,
            including the device's actual default sample rate as
            reported by PortAudio.
        _sample_rate_hz: Sample rate, in hertz, audio is captured at.
        _channels: Number of audio channels captured.
        _blocksize: Number of frames captured per audio block.
        _stream: The underlying ``sounddevice.InputStream``, or
            ``None`` if the device has not been opened.
        _is_open: Whether the device is currently open.
        _is_recording: Whether the device is currently recording.
        _audio_queue: Thread-safe queue buffering captured audio blocks
            as raw bytes.
    """

    def __init__(
        self,
        device_id: str | int | None = None,
        sample_rate_hz: int = 16_000,
        channels: int = 1,
        blocksize: int = 1024,
    ) -> None:
        """Resolves and describes the input device to be used.

        Args:
            device_id: Identifier of the input device to use, as
                accepted by ``sounddevice`` (an integer index or a
                device name substring). If ``None``, the platform's
                default input device is used.
            sample_rate_hz: Sample rate, in hertz, to capture audio at.
            channels: Number of audio channels to capture.
            blocksize: Number of frames to capture per audio block.

        Raises:
            MicrophoneError: If the requested device cannot be resolved
                or queried.
        """


        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be greater than zero.")

        if channels <= 0:
            raise ValueError("channels must be greater than zero.")

        if blocksize <= 0:
            raise ValueError("blocksize must be greater than zero.")



        try:
            resolved_id = device_id if device_id is not None else sd.default.device[0]
            device_query: dict[str, Any] = sd.query_devices(resolved_id, "input")
            default_input_id = sd.default.device[0]
        except Exception as exc:
            raise MicrophoneError(
                "Failed to resolve or query the requested input device.",
                details={"device_id": device_id},
            ) from exc

        actual_sample_rate = int(device_query["default_samplerate"])

        self._device_info = MicrophoneDeviceInfo(
            device_id=str(resolved_id),
            name=str(device_query["name"]),
            sample_rate_hz=actual_sample_rate,
            channels=int(device_query["max_input_channels"]),
            is_default=(resolved_id == default_input_id),
        )


        self._sample_rate_hz = sample_rate_hz
        self._channels = channels
        self._blocksize = blocksize
        self._stream: sd.InputStream | None = None
        self._is_open = False
        self._is_recording = False


        self._audio_queue: queue.Queue[bytes] = queue.Queue(
            maxsize=_DEFAULT_AUDIO_QUEUE_SIZE
        )


    @property
    def device_info(self) -> MicrophoneDeviceInfo:
        """Returns metadata describing this microphone device.

        Returns:
            The device's identifying and audio-format metadata.
        """
        return self._device_info

    @property
    def is_open(self) -> bool:
        """Whether the microphone device is currently open.

        Returns:
            ``True`` if ``open`` has been called successfully and
            ``close`` has not since been called, ``False`` otherwise.
        """
        return self._is_open

    @property
    def is_recording(self) -> bool:
        """Whether the microphone is currently capturing audio.

        Returns:
            ``True`` if ``start_recording`` has been called
            successfully and ``stop_recording`` has not since been
            called, ``False`` otherwise.
        """
        return self._is_recording

    def open(self) -> None:
        """Opens the microphone device and prepares it for recording.

        Creates the underlying ``sounddevice.InputStream`` and forces
        PortAudio to actually open the stream by briefly starting and
        immediately stopping it. Constructing an ``InputStream`` alone
        does not open the underlying PortAudio stream on every
        backend, so this round trip guarantees the device is genuinely
        opened while leaving it in a stopped state. Recording proper
        begins only once ``start_recording`` is called.

        Raises:
            MicrophoneError: If the device is already open, or the
                input stream cannot be created or opened.
        """
        if self._is_open:
            raise MicrophoneError(
                "Cannot open a microphone device that is already open.",
                details={"device_id": self._device_info.device_id},
            )
        try:
            self._stream = sd.InputStream(
                device=int(self._device_info.device_id),
                samplerate=self._sample_rate_hz,
                channels=self._channels,
                blocksize=self._blocksize,
                dtype=_DEFAULT_DTYPE,
                callback=self._on_audio_block,
            )
            self._stream.start()
            self._stream.stop()
        except Exception as exc:
            self._stream = None
            raise MicrophoneError(
                "Failed to create the input stream for the microphone device.",
                details={"device_id": self._device_info.device_id},
            ) from exc
        self._is_open = True

    def close(self) -> None:
        """Closes the microphone device and releases its resources.

        Stops recording first if it is currently in progress, then
        closes and releases the underlying input stream.

        Raises:
            MicrophoneError: If the device is not open, or the stream
                fails to close cleanly.
        """
        if not self._is_open or self._stream is None:
            raise MicrophoneError(
                "Cannot close a microphone device that is not open.",
                details={"device_id": self._device_info.device_id},
            )
        if self._is_recording:
            self.stop_recording()
        try:
            self._stream.close()
        except Exception as exc:
            raise MicrophoneError(
                "Failed to close the microphone input stream.",
                details={"device_id": self._device_info.device_id},
            ) from exc
        finally:
            self._stream = None
            self._is_open = False

    def start_recording(self) -> None:
        """Begins capturing audio from the microphone device.

        Clears any previously buffered audio blocks before starting.

        Raises:
            MicrophoneError: If the device is not open, is already
                recording, or the input stream fails to start.
        """
        if not self._is_open or self._stream is None:
            raise MicrophoneError(
                "Cannot start recording on a microphone device that is not open.",
                details={"device_id": self._device_info.device_id},
            )
        if self._is_recording:
            raise MicrophoneError(
                "Cannot start recording on a microphone device that is already recording.",
                details={"device_id": self._device_info.device_id},
            )
        self._drain_queue()
        try:
            self._stream.start()
        except Exception as exc:
            raise MicrophoneError(
                "Failed to start the microphone input stream.",
                details={"device_id": self._device_info.device_id},
            ) from exc
        self._is_recording = True

    def stop_recording(self) -> None:
        """Stops capturing audio from the microphone device.

        Any audio blocks buffered during the recording session are
        discarded once the stream has stopped, so stale audio does not
        leak into the next recording session.

        Raises:
            MicrophoneError: If the device is not currently recording,
                or the input stream fails to stop.
        """
        if not self._is_recording or self._stream is None:
            raise MicrophoneError(
                "Cannot stop recording on a microphone device that is not recording.",
                details={"device_id": self._device_info.device_id},
            )
        try:
            self._stream.stop()
        except Exception as exc:
            raise MicrophoneError(
                "Failed to stop the microphone input stream.",
                details={"device_id": self._device_info.device_id},
            ) from exc
        finally:
            self._is_recording = False
            self._drain_queue()

    def read_frame(self) -> bytes:
        """Reads the next available audio frame from the device.

        Blocks until a captured audio block becomes available or the
        internal read timeout elapses.

        Returns:
            Raw PCM audio data for a single captured block, encoded as
            signed 16-bit little-endian samples.

        Raises:
            MicrophoneError: If the device is not currently recording,
                or no audio block becomes available before the read
                timeout elapses.
        """
        if not self._is_recording:
            raise MicrophoneError(
                "Cannot read a frame from a microphone device that is not recording.",
                details={"device_id": self._device_info.device_id},
            )
        try:
            return self._audio_queue.get(timeout=_DEFAULT_READ_TIMEOUT_SECONDS)
        except queue.Empty as exc:
            raise MicrophoneError(
                "Timed out waiting for the next audio frame.",
                details={"device_id": self._device_info.device_id},
            ) from exc

    @classmethod
    def enumerate_devices(cls) -> list[MicrophoneDeviceInfo]:
        """Lists the input devices available on the current platform.

        Returns:
            Metadata for every audio device reporting at least one
            input channel.

        Raises:
            MicrophoneError: If available devices cannot be
                enumerated.
        """
        try:
            devices: list[dict[str, Any]] = sd.query_devices()
            default_input_id = sd.default.device[0]
        except Exception as exc:
            raise MicrophoneError("Failed to enumerate input devices.") from exc

        return [
            MicrophoneDeviceInfo(
                device_id=str(index),
                name=str(device["name"]),
                sample_rate_hz=int(device["default_samplerate"]),
                channels=int(device["max_input_channels"]),
                is_default=(index == default_input_id),
            )
            for index, device in enumerate(devices)
            if device.get("max_input_channels", 0) > 0
        ]

    def _on_audio_block(
        self,
        indata: Any,
        frames: int,
        time_info: Any,
        status: sd.CallbackFlags,
    ) -> None:
        """Buffers a single captured audio block from the input stream.

        Invoked by ``sounddevice`` on its internal audio callback
        thread whenever a new block of audio has been captured. Blocks
        reported with a non-zero ``status`` (e.g. an input overflow or
        underflow) are dropped rather than buffered, since such blocks
        may be incomplete or corrupted.

        Args:
            indata: Captured audio samples for this block, as a NumPy
                array.
            frames: Number of frames contained in this block.
            time_info: Timing information supplied by PortAudio for
                this block.
            status: Flags describing any overflow or underflow
                conditions for this block.
        """
        if status:
            return
        try:
            self._audio_queue.put_nowait(indata.tobytes())

        except queue.Full:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                pass

            try:
                self._audio_queue.put_nowait(indata.tobytes())
            except queue.Full:
                pass

    def _drain_queue(self) -> None:
        """Discards any audio blocks buffered from a previous recording."""
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
