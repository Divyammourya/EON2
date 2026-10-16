"""Audio backend abstraction for the EON Voice module.

This module defines ``AudioBackend``, the abstract interface
representing a complete audio subsystem for the Voice module. An
``AudioBackend`` abstracts an entire audio subsystem: it owns and
exposes the microphone and speaker implementations used for a given
platform or library, and manages their shared lifecycle.

Higher-level services in the Voice module depend only on this
abstraction, never on any specific audio library. Concrete
implementations of ``AudioBackend`` are responsible for wrapping a
particular audio library (e.g. SoundDevice, PyAudio, PortAudio,
WASAPI, CoreAudio, ALSA) and constructing the ``Microphone`` and
``Speaker`` instances appropriate to that library. ``VoiceManager`` and
the speech-to-text and text-to-speech providers never import or depend
on any concrete audio library directly; they interact exclusively
through ``AudioBackend``, ``Microphone``, and ``Speaker``.

Design notes:
    - ``AudioBackend`` defines *only* the contract that audio backend
      implementations must fulfill. It contains no implementation,
      backend-specific logic, logging, or I/O, so it can be depended
      upon by higher-level services without coupling them to any
      concrete audio library (Dependency Inversion Principle).
    - Microphone and speaker access are exposed as properties owned by
      the backend, keeping device construction and ownership in one
      place rather than scattered across the module (Single
      Responsibility Principle).
    - Lifecycle management (``initialize`` / ``shutdown`` /
      ``health_check``) is kept separate from device access, so
      consumers can depend on only the subset of behavior they need
      (Interface Segregation Principle).
    - Any concrete subclass must be substitutable anywhere an
      ``AudioBackend`` is expected, with consistent behavior implied by
      this contract (Liskov Substitution Principle).
    - New audio backends are added by creating new subclasses; this
      module never needs to change to support them (Open/Closed
      Principle).

Requires: Python 3.12+
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.modules.voice.microphone import Microphone
from src.modules.voice.speaker import Speaker


class AudioBackend(ABC):
    """Abstract base class for all audio backend implementations.

    An ``AudioBackend`` encapsulates the lifecycle of an entire audio
    subsystem and owns the concrete ``Microphone`` and ``Speaker``
    instances used to capture and play audio. Concrete subclasses are
    responsible for all backend-specific logic, library integration,
    and error handling; this class defines only the contract they must
    satisfy.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the unique, human-readable name of this backend.

        Returns:
            The backend's name (e.g. "sounddevice", "pyaudio",
            "portaudio", "wasapi", "coreaudio", "alsa").
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def microphone(self) -> Microphone:
        """Returns the microphone owned by this backend.

        Returns:
            The ``Microphone`` instance this backend provides for
            audio capture.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def speaker(self) -> Speaker:
        """Returns the speaker owned by this backend.

        Returns:
            The ``Speaker`` instance this backend provides for audio
            playback.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def initialized(self) -> bool:
        """Whether this backend has been successfully initialized.

        Returns:
            ``True`` if ``initialize`` has been called successfully and
            ``shutdown`` has not since been called, ``False``
            otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def initialize(self) -> None:
        """Prepares the backend and its owned devices for use.

        Implementations should perform any setup required before the
        microphone and speaker can be opened and used (e.g. loading the
        underlying audio library, enumerating devices, allocating
        shared resources).

        Raises:
            VoiceInitializationError: If the backend fails to
                initialize.
        """
        raise NotImplementedError

    @abstractmethod
    def shutdown(self) -> None:
        """Releases all resources held by the backend and its devices.

        Implementations should perform any teardown required to
        cleanly release resources acquired during ``initialize`` or
        subsequent use, including closing the microphone and speaker if
        they remain open.

        Raises:
            VoiceProviderError: If the backend fails to shut down
                cleanly.
        """
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """Reports whether the backend is currently healthy and usable.

        Returns:
            ``True`` if the backend is initialized and its devices are
            able to service requests, ``False`` otherwise.
        """
        raise NotImplementedError
