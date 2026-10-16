# Voice Architecture

## Purpose

This document describes the architecture of the EON Voice module, including its responsibilities, abstractions, lifecycle, provider model, and interactions with the rest of the system.

The Voice module is responsible for speech recognition and speech synthesis while remaining completely independent of any specific speech engine or vendor.

---

# Goals

The Voice module is designed to achieve the following goals:

- Modular design
- Provider independence
- Offline and online support
- Thread safety
- Testability
- Explicit resource lifecycle
- Consistent error handling

---

# Responsibilities

The Voice module is responsible for:

- Speech recognition
- Speech synthesis
- Voice session management
- Provider abstraction
- Audio transport
- Voice configuration
- Voice-specific exceptions
- Speech request and response models

The Voice module is not responsible for:

- Conversation management
- LLM interaction
- Memory management
- Audio playback
- User interface

---

# High-Level Architecture

```text
                   Application
                        │
                        ▼
                 Voice Manager
                        │
        ┌───────────────┼───────────────┐
        │                               │
 Speech Recognition             Speech Synthesis
        │                               │
        ▼                               ▼
SpeechToTextProvider          TextToSpeechProvider
        │                               │
   ┌────┴─────┐                 ┌───────┴────────┐
   │          │                 │                │
OpenAI   FasterWhisper      OpenAI          Piper
```

---

# Module Organization

```text
voice/
├── exceptions.py
├── models.py
├── providers/
│   ├── base.py
│   ├── stt.py
│   ├── tts.py
│   ├── openai.py
│   ├── piper.py
│   └── faster_whisper.py
```

Each provider implementation is isolated from the rest of the module.

---

# Provider Architecture

The Voice module follows the Provider Pattern.

High-level code communicates only through provider interfaces.

Concrete providers encapsulate third-party SDKs and external libraries.

Benefits include:

- Replaceable implementations
- Easier testing
- Reduced coupling
- Vendor independence

---

# Provider Hierarchy

```text
                 VoiceProvider
                 /           \
                /             \
SpeechToTextProvider   TextToSpeechProvider
        │                      │
        │                      │
  FasterWhisper          PiperProvider
        │
        └────────────┐
                     │
              OpenAIProvider
```

OpenAIProvider implements the complete VoiceProvider interface because it supports both speech recognition and speech synthesis.

PiperProvider implements only TextToSpeechProvider.

FasterWhisperProvider implements only SpeechToTextProvider.

---

# Voice Sessions

Every voice interaction occurs within a VoiceSession.

A session represents the state associated with one conversation or voice interaction.

Responsibilities include:

- Session identity
- Configuration
- Metadata
- Language information

Providers do not own sessions.

They only register and manage active session identifiers.

---

# Session Lifecycle

```text
Create Session
      │
      ▼
Start Session
      │
      ▼
Voice Operations
      │
      ▼
Stop Session
      │
      ▼
Cleanup
```

Providers validate that operations occur only on active sessions.

---

# Audio Transport

Audio is exchanged through session metadata.

Current convention:

```text
session.metadata["audio_bytes"]
```

Speech recognition providers read audio bytes from this location.

Speech synthesis providers write synthesized audio bytes back to the same location.

Providers never play audio directly.

Providers never write files to disk.

---

# Speech Recognition Flow

```text
Audio Bytes
      │
      ▼
VoiceSession
      │
      ▼
SpeechToTextProvider
      │
      ▼
Concrete Provider
      │
      ▼
SpeechRecognitionResult
```

Recognition providers produce immutable result objects.

---

# Speech Synthesis Flow

```text
SpeechSynthesisRequest
          │
          ▼
TextToSpeechProvider
          │
          ▼
Concrete Provider
          │
          ▼
Audio Bytes
          │
          ▼
VoiceSession Metadata
```

Playback is handled elsewhere in the application.

---

# Thread Safety

Providers are responsible for protecting their own mutable state.

Typical synchronization includes:

- Client initialization locks
- Model loading locks
- Inference locks
- Session registration locks

Thread safety is an implementation detail.

Callers should not need external synchronization.

---

# Lazy Initialization

Heavy resources are initialized only when first required.

Examples include:

- OpenAI clients
- Piper models
- Faster Whisper models

Advantages:

- Faster startup
- Reduced memory usage
- Delayed failure until resource usage
- Optional provider initialization

---

# Exception Translation

Third-party exceptions are never exposed outside provider implementations.

Instead:

```text
Third-Party Exception
        │
        ▼
Voice Exception
        │
        ▼
Application
```

Common exception types include:

- VoiceInitializationError
- VoiceProviderError
- VoiceSessionError
- SpeechRecognitionError
- SpeechSynthesisError

---

# Provider Responsibilities

Each provider is responsible for:

- Resource initialization
- Resource cleanup
- Session validation
- Request validation
- Exception translation
- Thread safety
- Provider-specific implementation details

Providers should not coordinate application behavior.

---

# Data Models

Primary models include:

- VoiceSession
- VoiceConfiguration
- SpeechRecognitionResult
- SpeechSynthesisRequest

Models contain data only.

Business logic belongs within providers or services.

---

# Design Principles

The Voice module follows:

- Single Responsibility Principle
- Dependency Inversion Principle
- Open/Closed Principle
- Composition over Inheritance
- Explicit Lifecycle Management

These principles ensure that new providers can be added without modifying existing implementations.

---

# Future Expansion

The Voice architecture is designed to support future providers.

Potential additions include:

- ElevenLabs
- Azure Speech
- Google Speech
- Coqui TTS
- Vosk
- Deepgram
- Amazon Polly
- Amazon Transcribe

Adding a provider should require only a new implementation of the appropriate provider interface.

---

# Related Documents

- overview.md
- components.md
- directory_structure.md
- ../modules/voice.md
- ../decisions/ADR-0001-provider-pattern.md
- ../decisions/ADR-0002-session-lifecycle.md
