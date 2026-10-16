"""Speaker device abstraction for the EON Voice module.

This module defines the abstract interface that every speaker
implementation must satisfy in order to supply audio output for the
Voice module. It contains no concrete audio backend logic: no
dependency on any specific audio library (e.g. ``sounddevice``,
``pyaudio``, ``portaudio``) is permitted here or in any code that
depends on this module for its abstractions.

Design notes:
    - ``Speaker`` defines *only* the contract that speaker
      implementations must fulfill. It contains no implementation,
      backend-specific logic, logging, or I/O, so it can be depended
      upon by higher-level services without coupling them to any
      concrete audio library (Dependency Inversion Principle).
    - Device metadata is captured in ``SpeakerDeviceInfo``, a plain
      data holder kept separate from behavior, so metadata can be
      inspected, serialized, or compared without invoking any device
      operation (Single Responsibility Principle).
    - Each abstract method represents a single, cohesive responsibility
      (lifecycle, playback control, device discovery), allowing
      concrete implementations to be composed and substituted freely
      (Interface Segregation Principle, Liskov Substitution Principle).
    - New speaker backends are added by creating new subclasses; this
      module never needs to change to support them (Open/Closed
      Principle).

Requires: Python 3.12+
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class SpeakerDeviceInfo:
    """Describes the identity and audio characteristics of a speaker.

    Attributes:
        device_id: Unique identifier of the speaker device, as assigned
            by the underlying platform or audio backend.
        name: Human-readable name of the speaker device.
        sample_rate_hz: Sample rate, in hertz, that the device outputs
            audio at.
        channels: Number of audio channels the device outputs (e.g.
            ``1`` for mono, ``2`` for stereo).
        is_default: Whether this device is the platform's default
            output device.
    """

    device_id: str
    name: str
    sample_rate_hz: int
    channels: int
    is_default: bool = False


class Speaker(ABC):
    """Abstract base class for all speaker device implementations.

    A ``Speaker`` encapsulates the lifecycle, playback control, and
    device discovery of a specific audio output device. Concrete
    subclasses are responsible for all backend-specific logic, device
    I/O, and error handling; this class defines only the contract they
    must satisfy.
    """

    @property
    @abstractmethod
    def device_info(self) -> SpeakerDeviceInfo:
        """Returns metadata describing this speaker device.

        Returns:
            The device's identifying and audio-format metadata.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Whether the speaker device is currently open.

        Returns:
            ``True`` if ``open`` has been called successfully and
            ``close`` has not since been called, ``False`` otherwise.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def is_playing(self) -> bool:
        """Whether the speaker is currently outputting audio.

        Returns:
            ``True`` if audio is actively being played back, ``False``
            otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def open(self) -> None:
        """Opens the speaker device and prepares it for playback.

        Implementations should perform any setup required before
        playback can begin (e.g. acquiring the device, allocating
        buffers, validating permissions).

        Raises:
            SpeakerError: If the device cannot be opened.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Closes the speaker device and releases its resources.

        Implementations should stop any active playback and release
        all resources acquired during ``open``.

        Raises:
            SpeakerError: If the device fails to close cleanly.
        """
        raise NotImplementedError

    @abstractmethod
    def play(self, audio: bytes) -> None:
        """Plays raw audio data through the speaker device.

        Args:
            audio: Raw audio data to play, encoded according to the
                device's configured sample rate and channel count.

        Raises:
            SpeakerError: If the device is not open or the audio
                cannot otherwise be played.
        """
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Stops any audio currently being played through the device.

        Raises:
            SpeakerError: If playback cannot be stopped.
        """
        raise NotImplementedError

    @abstractmethod
    def flush(self) -> None:
        """Discards any buffered, not-yet-played audio data.

        Raises:
            SpeakerError: If the device's buffered audio cannot be
                flushed.
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def enumerate_devices(cls) -> list[SpeakerDeviceInfo]:
        """Lists the speaker devices available on the current platform.

        Returns:
            Metadata for every speaker device currently available.

        Raises:
            SpeakerError: If available devices cannot be enumerated.
        """
        raise NotImplementedError
