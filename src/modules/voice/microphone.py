"""Microphone device abstraction for the EON Voice module.

This module defines the abstract interface that every microphone
implementation must satisfy in order to supply audio input to the
Voice module. It contains no concrete audio backend logic: no
dependency on any specific audio library (e.g. ``sounddevice``,
``pyaudio``, ``portaudio``) is permitted here or in any code that
depends on this module for its abstractions.

Design notes:
    - ``Microphone`` defines *only* the contract that microphone
      implementations must fulfill. It contains no implementation,
      backend-specific logic, logging, or I/O, so it can be depended
      upon by higher-level services without coupling them to any
      concrete audio library (Dependency Inversion Principle).
    - Device metadata is captured in ``MicrophoneDeviceInfo``, a plain
      data holder kept separate from behavior, so metadata can be
      inspected, serialized, or compared without invoking any device
      operation (Single Responsibility Principle).
    - Each abstract method represents a single, cohesive responsibility
      (lifecycle, recording control, frame reading), allowing concrete
      implementations to be composed and substituted freely (Interface
      Segregation Principle, Liskov Substitution Principle).
    - New microphone backends are added by creating new subclasses;
      this module never needs to change to support them (Open/Closed
      Principle).

Requires: Python 3.12+
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class MicrophoneDeviceInfo:
    """Describes the identity and audio characteristics of a microphone.

    Attributes:
        device_id: Unique identifier of the microphone device, as
            assigned by the underlying platform or audio backend.
        name: Human-readable name of the microphone device.
        sample_rate_hz: Sample rate, in hertz, that the device captures
            audio at.
        channels: Number of audio channels the device captures (e.g.
            ``1`` for mono, ``2`` for stereo).
        is_default: Whether this device is the platform's default input
            device.
    """

    device_id: str
    name: str
    sample_rate_hz: int
    channels: int
    is_default: bool = False


class Microphone(ABC):
    """Abstract base class for all microphone device implementations.

    A ``Microphone`` encapsulates the lifecycle, recording control, and
    audio frame delivery of a specific audio input device. Concrete
    subclasses are responsible for all backend-specific logic, device
    I/O, and error handling; this class defines only the contract they
    must satisfy.
    """

    @property
    @abstractmethod
    def device_info(self) -> MicrophoneDeviceInfo:
        """Returns metadata describing this microphone device.

        Returns:
            The device's identifying and audio-format metadata.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Whether the microphone device is currently open.

        Returns:
            ``True`` if ``open`` has been called successfully and
            ``close`` has not since been called, ``False`` otherwise.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def is_recording(self) -> bool:
        """Whether the microphone is currently capturing audio.

        Returns:
            ``True`` if ``start_recording`` has been called
            successfully and ``stop_recording`` has not since been
            called, ``False`` otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def open(self) -> None:
        """Opens the microphone device and prepares it for recording.

        Implementations should perform any setup required before
        recording can begin (e.g. acquiring the device, allocating
        buffers, validating permissions).

        Raises:
            MicrophoneError: If the device cannot be opened.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Closes the microphone device and releases its resources.

        Implementations should stop any active recording and release
        all resources acquired during ``open``.

        Raises:
            MicrophoneError: If the device fails to close cleanly.
        """
        raise NotImplementedError

    @abstractmethod
    def start_recording(self) -> None:
        """Begins capturing audio from the microphone device.

        Raises:
            MicrophoneError: If the device is not open, is already
                recording, or recording cannot otherwise be started.
        """
        raise NotImplementedError

    @abstractmethod
    def stop_recording(self) -> None:
        """Stops capturing audio from the microphone device.

        Raises:
            MicrophoneError: If the device is not currently recording
                or recording cannot otherwise be stopped.
        """
        raise NotImplementedError

    @abstractmethod
    def read_frame(self) -> bytes:
        """Reads the next available audio frame from the device.

        Returns:
            Raw audio data for a single captured frame, encoded
            according to the device's configured sample rate and
            channel count.

        Raises:
            MicrophoneError: If the device is not currently recording
                or the frame cannot be read.
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def enumerate_devices(cls) -> list[MicrophoneDeviceInfo]:
        """Returns all microphone devices available on the system.

        Returns:
            Metadata describing every detected microphone device.

        Raises:
            MicrophoneError: If available devices cannot be enumerated.
        """
        raise NotImplementedError
