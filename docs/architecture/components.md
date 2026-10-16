# Components Architecture

## Purpose

This document describes the major architectural components of EON, their responsibilities, boundaries, dependencies, and interactions. It serves as a reference for understanding how the system is decomposed into independent subsystems.

---

# Component Overview

EON is composed of independent feature-oriented modules supported by shared infrastructure.

```text
                    EON
                     │
     ┌───────────────┼───────────────┐
     │               │               │
 Application      Core Modules   Infrastructure
                     │
      ┌──────────────┼──────────────┐
      │              │              │
    Voice         Memory          LLM
      │
      │
 Provider Implementations
```

Each component has a clearly defined responsibility and communicates with other components through well-defined interfaces.

---

# Application Layer

## Purpose

The Application Layer coordinates the overall execution of EON.

It contains the high-level orchestration logic responsible for managing conversations, coordinating modules, and controlling the application's lifecycle.

---

## Responsibilities

- Application startup
- Application shutdown
- Session management
- Conversation orchestration
- Module coordination
- Configuration loading

---

## Dependencies

The Application Layer depends on public interfaces exposed by feature modules.

It should never depend on implementation details.

---

# Voice Module

## Purpose

The Voice module provides speech recognition and speech synthesis capabilities.

It abstracts both local and cloud-based speech providers behind common interfaces.

---

## Responsibilities

- Speech recognition
- Speech synthesis
- Voice session management
- Provider abstraction
- Audio metadata management
- Voice configuration
- Voice-specific exceptions

---

## Public Interfaces

- VoiceProvider
- SpeechToTextProvider
- TextToSpeechProvider

---

## Current Providers

Speech Recognition

- FasterWhisperProvider
- OpenAIProvider

Speech Synthesis

- PiperProvider
- OpenAIProvider

---

## Dependencies

Depends on

- Voice Models
- Provider Interfaces
- Voice Exceptions

Never depends directly on other EON modules.

---

# Memory Module

## Status

Planned

---

## Purpose

The Memory module will manage conversational memory and long-term knowledge.

---

## Planned Responsibilities

- Short-term memory
- Long-term memory
- Memory retrieval
- Memory summarization
- Memory persistence
- Context assembly

---

## Planned Dependencies

- Storage
- Embedding providers
- LLM module

---

# LLM Module

## Status

Planned

---

## Purpose

The LLM module will provide a unified interface for interacting with language models.

---

## Planned Responsibilities

- Prompt construction
- Completion generation
- Tool calling
- Function execution
- Structured output generation
- Provider abstraction

---

## Planned Providers

- OpenAI
- Ollama
- Local models
- Future hosted providers

---

# Plugin System

## Status

Planned

---

## Purpose

The Plugin System will allow external functionality to extend EON without modifying core code.

---

## Planned Responsibilities

- Plugin discovery
- Plugin loading
- Dependency resolution
- Lifecycle management
- Permission management

---

# Storage Layer

## Status

Planned

---

## Purpose

The Storage Layer will provide persistent storage for EON.

---

## Planned Responsibilities

- Database access
- File storage
- Embedding storage
- Configuration persistence
- Cache management

---

# Configuration System

## Purpose

The configuration system centralizes application configuration.

---

## Responsibilities

- Environment variables
- Configuration validation
- Default values
- Runtime configuration

---

## Design Principles

Configuration should be

- Explicit
- Typed
- Validated
- Immutable whenever possible

---

# Logging System

## Purpose

The logging system records operational information for debugging and monitoring.

---

## Responsibilities

- Structured logging
- Error logging
- Diagnostic information
- Performance logging

---

# Exception System

## Purpose

The exception system provides project-wide error abstractions.

---

## Responsibilities

- Consistent error hierarchy
- Third-party exception translation
- Diagnostic information
- Error propagation

---

# Provider Layer

## Purpose

The Provider Layer isolates external libraries and services behind interfaces defined by EON.

---

## Responsibilities

- Third-party SDK integration
- Resource management
- Exception translation
- Provider lifecycle
- Vendor abstraction

---

## Current Providers

### Voice

- OpenAIProvider
- FasterWhisperProvider
- PiperProvider

---

## Future Providers

- OllamaProvider
- AzureOpenAIProvider
- GoogleProvider
- ElevenLabsProvider

---

# Shared Models

Shared models represent immutable data exchanged between components.

Examples include

- Sessions
- Requests
- Responses
- Configuration objects
- Result objects

Models should contain data only.

Business logic belongs in services.

---

# Component Communication

Components communicate through public interfaces.

```text
Application
      │
      ▼
Module Interface
      │
      ▼
Service
      │
      ▼
Provider Interface
      │
      ▼
Concrete Provider
```

Direct communication with implementation classes should be avoided.

---

# Dependency Rules

Components may depend only on lower architectural layers.

Allowed

```text
Application
      ↓
Modules
      ↓
Providers
      ↓
External Libraries
```

Forbidden

```text
Provider
      ↓
Application
```

or

```text
Voice Module
      ↓
Memory Internal Classes
```

Cross-module dependencies should occur only through public interfaces.

---

# Lifecycle Responsibilities

Each component is responsible for managing its own resources.

Typical lifecycle

```text
Initialize

↓

Start

↓

Operate

↓

Stop

↓

Shutdown
```

Components should clean up all allocated resources during shutdown.

---

# Thread Safety

Each component is responsible for protecting its own mutable state.

Synchronization must be implemented internally rather than delegated to callers.

Typical synchronization includes

- Initialization locks
- Session locks
- Inference locks

---

# Extensibility

New functionality should be added by extending existing interfaces rather than modifying existing implementations.

Examples

- Add a new provider
- Add a new module
- Add a new plugin
- Add a new storage backend

Existing code should require minimal modification.

---

# Related Documents

- overview.md
- directory_structure.md
- voice.md
- ../modules/README.md
- ../decisions/
```
