"""
Voice Configuration.

Configuration models for the Voice subsystem.

This module contains only configuration data: no provider
construction, no I/O, and no third-party imports. Concrete providers
are selected and built by the composition root (``bootstrap/services.py``)
based on the values held here, keeping this module free of any
dependency on ``faster_whisper``, ``piper``, or the OpenAI SDK
(Open/Closed Principle, Dependency Inversion Principle).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class VoiceServiceConfig:
    """
    Configuration for the Voice subsystem.

    Attributes:
        stt_provider: Which speech-to-text provider to construct.
            One of "faster_whisper", "openai".
        tts_provider: Which text-to-speech provider to construct.
            One of "piper", "openai".
        language_code: Default BCP-47 language code for new sessions,
            or ``None``/``"auto"`` to let the STT provider auto-detect
            the spoken language per utterance instead of forcing one.
            Auto-detect is the default so Hindi/Hinglish speech isn't
            forced through an English hint (see
            ``FasterWhisperProvider._resolve_language_hint``). Set this
            to an explicit BCP-47 code (e.g. "en-US", "hi-IN") to pin
            recognition to a single language, e.g. if auto-detection is
            unreliable for a particular microphone/accent.
        sample_rate_hz: Sample rate, in hertz, used for microphone
            capture and expected by the STT provider.
        listen_seconds: Default duration to record when capturing a
            single utterance via ``VoiceService.listen_once``.
        faster_whisper: Constructor kwargs for ``FasterWhisperProvider``.
        piper: Constructor kwargs for ``PiperProvider``, used as the
            default synthesis voice.
        piper_hi: Optional constructor kwargs for a second
            ``PiperProvider`` voice used to reply when the detected
            input language for a turn was Hindi-dominant. ``None``
            (the default) means no Hindi voice is configured; Piper
            falls back to the default voice and logs that Hindi TTS
            isn't available. Hindi Piper voices can be downloaded from
            the rhasspy/piper-voices repository on Hugging Face
            (https://huggingface.co/rhasspy/piper-voices) — pick a
            "hi_IN" voice, download its ``.onnx`` and ``.onnx.json``
            files, and point ``model_path``/``config_path`` here. This
            is an external asset the user must fetch themselves, same
            as the default English Piper voice.
        openai: Constructor kwargs for ``OpenAIProvider``, shared by
            both the STT and TTS roles when "openai" is selected for
            either of them.
    """

    stt_provider: str = "faster_whisper"
    tts_provider: str = "piper"

    # ``None`` requests Whisper auto-detection. A literal "auto" is
    # also accepted as an explicit synonym for "don't pin a language" —
    # see FasterWhisperProvider._resolve_language_hint, which maps both
    # to `language=None` in the underlying transcribe() call.
    language_code: str | None = None
    sample_rate_hz: int = 16_000
    listen_seconds: float = 5.0

    # Default synthesis tuning, used when a request doesn't override
    # them. Tying these to a personality preset (e.g. a lower,
    # measured voice for "jarvis") is a natural extension point.
    voice_id: str | None = None
    speaking_rate: float = 1.0

    # Wake-word listening. There is no pretrained neural wake-word model
    # for an arbitrary custom word like "EON" (engines such as
    # openWakeWord/Porcupine ship fixed phrases, e.g. "hey jarvis"), so
    # the wake-word listener instead reuses the already-loaded STT
    # provider on short rolling windows, gated by a cheap energy (VAD)
    # check so it only transcribes when something was actually said.
    wake_word: str = "eon"
    wake_word_enabled: bool = True
    wake_word_window_seconds: float = 2.0
    wake_word_check_interval_seconds: float = 0.5
    wake_word_energy_threshold: float = 300.0

    # Per-utterance listening (endpointing). Instead of recording for a
    # fixed number of seconds, EON records until the speaker has been
    # silent for ``silence_end_seconds`` — so a one-word answer returns
    # immediately and a long question isn't cut off — with a hard cap of
    # ``listen_max_seconds`` so constant background noise can't record
    # forever. ``listen_min_speech_seconds`` is the least amount of
    # actual speech a recording must contain to count as an utterance.
    silence_end_seconds: float = 0.8
    listen_max_seconds: float = 15.0
    listen_min_speech_seconds: float = 0.3
    # How long to wait for speech to *begin* on a one-off listen before
    # deciding the user said nothing.
    listen_start_timeout_seconds: float = 5.0

    # Continuous conversation mode. After the wake word, EON keeps
    # listening for follow-up turns without the user having to say the
    # wake word again, until they go quiet for
    # ``conversation_idle_timeout_seconds`` or say an exit phrase (see
    # ``conversation_exit_phrases``). Set ``conversation_mode_enabled``
    # to False to restore the old one-shot behaviour (wake word needed
    # for every turn).
    conversation_mode_enabled: bool = True
    conversation_idle_timeout_seconds: float = 12.0
    conversation_exit_phrases: tuple[str, ...] = (
        "goodbye",
        "good bye",
        "bye",
        "bye bye",
        "exit",
        "quit",
        "stop listening",
        "go to sleep",
        "that's all",
        "that is all",
        "thats all",
        "never mind",
        "nevermind",
        "we're done",
        "we are done",
        "i'm done",
        "im done",
    )

    # Owner voice recognition. A lightweight spectral + pitch
    # "voiceprint" (see SpeakerIdentifier) computed from the same audio
    # window used for wake-word detection — not a deep-learned speaker
    # embedding model (e.g. resemblyzer/speechbrain), deliberately, to
    # avoid pulling in a heavy torch-based dependency on a CPU-only
    # laptop. This means it's a soft, personalized-greeting signal
    # ("was that probably the enrolled owner?"), not a strong security
    # boundary — EON still answers anyone regardless of this check; it
    # only gates the "Welcome back, sir" greeting. Enroll via the
    # console: type "enroll voice".
    speaker_verification_enabled: bool = True
    speaker_profile_path: str = "data/voice/speaker_profile.npy"
    speaker_verification_threshold: float = 0.90
    speaker_enroll_seconds: float = 5.0

    faster_whisper: dict[str, Any] = field(
        default_factory=lambda: {
            "model_name": "base",
            "device": "cpu",
            "compute_type": "int8",
        }
    )

    piper: dict[str, Any] = field(
        default_factory=lambda: {
            "model_path": "data/voice/piper/voice.onnx",
            "config_path": "data/voice/piper/voice.onnx.json",
        }
    )

    # Optional second Piper voice used for Hindi-dominant replies. Left
    # unset (``None``) by default: no Hindi voice model ships with EON,
    # the user has to fetch one (see the ``piper_hi`` docstring entry
    # above). Example once downloaded:
    #   piper_hi = {
    #       "model_path": "data/voice/piper/voice_hi.onnx",
    #       "config_path": "data/voice/piper/voice_hi.onnx.json",
    #   }
    piper_hi: dict[str, Any] | None = None

    openai: dict[str, Any] = field(default_factory=dict)
