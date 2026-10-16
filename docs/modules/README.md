# EON Modules

## Purpose

This directory documents the major modules that make up EON.

Each module is designed around a single responsibility and exposes clear interfaces to the rest of the application. Modules communicate through abstractions rather than concrete implementations, allowing independent development, testing, and future replacement of implementations.

---

# Current Modules

## Voice

Responsible for all speech-related functionality.

Responsibilities include:

- Speech Recognition (STT)
- Speech Synthesis (TTS)
- Session Management
- Provider Management
- Voice Configuration

Documentation:

- voice.md

---

## Memory

Responsible for conversational memory and long-term knowledge.

Responsibilities include:

- Conversation Storage
- Memory Retrieval
- Embeddings
- Summarization
- Context Construction

Documentation:

- memory.md

---

## LLM

Responsible for communication with language models.

Responsibilities include:

- Prompt Construction
- Chat Completion
- Streaming
- Tool Calling
- Structured Output

Documentation:

- llm.md

---

# Module Design Philosophy

Every module follows the same architectural principles:

- Single Responsibility Principle
- Dependency Inversion Principle
- Open/Closed Principle
- Interface-Based Design
- Provider Pattern
- Explicit Lifecycle Management
- Exception Translation
- Thread Safety where required

---

# Module Independence

Modules should never directly depend on implementation details of other modules.

Communication should always occur through:

- Interfaces
- Abstract Base Classes
- Data Models
- Events (future)

---

# Standard Module Structure

Each module should generally contain:

```text
module/
│
├── manager.py
├── models.py
├── exceptions.py
├── interfaces.py
├── providers/
├── services/
├── config.py
├── utils.py
└── __init__.py
```

Some modules may contain additional directories depending on their complexity.

---

# Provider-Based Modules

Modules that interact with external systems should isolate those dependencies behind provider implementations.

Example:

```text
Voice Module

↓

VoiceProvider

↓

PiperProvider

↓

Piper SDK
```

Only provider implementations may import third-party SDKs.

---

# Future Modules

Potential future modules include:

- Agent
- Workflow
- Vision
- Plugins
- Scheduler
- Knowledge Graph
- Automation
- Networking

---

# Related Documents

- ../architecture/overview.md
- ../architecture/components.md
- ../architecture/system_diagrams.md
