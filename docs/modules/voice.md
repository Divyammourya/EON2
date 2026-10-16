# Voice Module

## Purpose

The Voice module provides all speech-related functionality within EON.

It is responsible for converting speech to text, converting text to speech, managing voice sessions, coordinating providers, and exposing a consistent interface to the rest of the application.

The module is completely independent of any specific speech engine or vendor.

---

# Responsibilities

The Voice module is responsible for:

- Speech Recognition (Speech-to-Text)
- Speech Synthesis (Text-to-Speech)
- Voice Session Management
- Provider Registration
- Provider Selection
- Voice Configuration
- Audio Transport
- Error Translation

The module is not responsible for:

- Audio playback
- Audio recording
- User interface
- Conversation management
- LLM communication

---

# High-Level Architecture

```text
Application
      │
      ▼
VoiceManager
      │
      ▼
VoiceProvider
      │
 ┌────┼─────────────────────────────┐
 │    │                             │
 ▼    ▼                             ▼
OpenAIProvider      FasterWhisperProvider     PiperProvider
```

The application communicates only with `VoiceManager`.

`VoiceManager` communicates only with the `VoiceProvider` abstraction.

Concrete providers communicate with external libraries.

---

# Major Components

## VoiceManager

Coordinates the lifecycle of voice providers and voice sessions.

Responsibilities include:

- Initializing providers
- Shutting down providers
- Starting sessions
- Stopping sessions
- Selecting providers
- Delegating speech operations

---

## VoiceProvider

Defines the common interface implemented by all voice providers.

Responsibilities include:

- Session lifecycle
- Speech recognition
- Speech synthesis
- Health checks

The rest of the application depends only on this abstraction.

---

## SpeechToTextProvider

Specialized provider for speech recognition.

Responsibilities:

- Audio transcription
- Streaming transcription

---

## TextToSpeechProvider

Specialized provider for speech synthesis.

Responsibilities:

- Speech generation
- Speaking control

---

## VoiceSession

Represents a single active conversation.

Stores:

- Session ID
- Configuration
- Metadata
- Runtime state

The session acts as the transport object between components.

---

## SpeechRecognitionResult

Represents a transcription result.

Contains:

- Transcript
- Confidence
- Language
- Final/Partial state

---

## SpeechSynthesisRequest

Represents a speech synthesis request.

Contains:

- Text
- Speaking rate
- Voice ID
- Request ID

---

# Current Providers

## FasterWhisperProvider

Provides offline speech recognition using Faster Whisper.

Capabilities:

- Speech-to-text
- Streaming transcription
- Offline inference

Does not support:

- Speech synthesis

---

## PiperProvider

Provides offline text-to-speech using Piper.

Capabilities:

- Speech synthesis
- Offline inference

Does not support:

- Speech recognition

---

## OpenAIProvider

Provides hosted speech services using OpenAI APIs.

Capabilities:

- Speech recognition
- Speech synthesis

Uses a single authenticated client for both operations.

---

# Session Lifecycle

```text
Create Session

↓

Start Session

↓

Speech Operations

↓

Stop Session

↓

Destroy Session
```

Providers validate that sessions are active before performing operations.

---

# Provider Selection

The VoiceManager selects the appropriate provider based on:

- Requested capability
- Provider availability
- Configuration
- Future policy rules

Provider implementations never select themselves.

---

# Error Handling

The module translates all provider-specific exceptions into Voice module exceptions.

Examples:

- VoiceInitializationError
- VoiceSessionError
- SpeechRecognitionError
- SpeechSynthesisError
- VoiceProviderError

No third-party exception types escape the Voice module.

---

# Thread Safety

Providers are responsible for their own thread safety.

Current implementations use:

- Lazy initialization
- Double-checked locking
- Session locks
- Inference locks

VoiceManager assumes providers are thread-safe.

---

# External Dependencies

Current provider dependencies:

- Faster Whisper
- Piper
- OpenAI SDK

These dependencies are isolated inside provider implementations.

---

# Future Enhancements

Planned improvements include:

- Streaming TTS
- Streaming OpenAI transcription
- Provider auto-selection
- Voice activity detection
- Audio preprocessing
- Provider health monitoring
- Voice caching
- Multi-provider failover

---

# Related Documents

- ../architecture/voice.md
- ../architecture/system_diagrams.md
- ../decisions/ADR-0001-provider-pattern.md
- ../decisions/ADR-0002-session-lifecycle.md
- ../decisions/ADR-0003-provider-selection.md
