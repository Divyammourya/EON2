# ADR-0003: Centralized Provider Selection

## Status

**Accepted**

---

# Context

EON is designed to support multiple implementations for the same capability.

Examples include:

### Voice

- FasterWhisper
- OpenAI
- Deepgram
- Whisper.cpp

### Text-to-Speech

- Piper
- OpenAI
- ElevenLabs
- Coqui

### LLM

- OpenAI
- Anthropic
- Gemini
- Ollama
- LM Studio

### Memory

- SQLite
- PostgreSQL
- ChromaDB
- FAISS
- Qdrant

Because multiple providers may implement the same interface, the application requires a consistent mechanism for deciding which implementation should be used.

Without a centralized strategy, provider selection logic would become duplicated across the codebase.

---

# Decision

Provider selection is centralized within manager classes.

Examples include:

- VoiceManager
- LLMManager
- MemoryManager

Managers are responsible for:

- Registering providers
- Selecting providers
- Initializing providers
- Health checking providers
- Switching providers
- Falling back to alternate providers
- Managing provider lifecycle

Providers are responsible only for implementing functionality.

They never choose themselves.

---

# Architecture

```text
Application
      │
      ▼
Manager
      │
      ▼
Provider Interface
      │
 ┌────┼───────────────────────┐
 │    │                       │
 ▼    ▼                       ▼
Provider A   Provider B   Provider C
```

Only managers know which provider is currently active.

The application communicates exclusively with the manager.

---

# Provider Responsibilities

Providers are responsible for:

- Implementing interfaces
- Managing internal resources
- Translating third-party exceptions
- Executing requested operations
- Reporting health status

Providers are **not** responsible for:

- Selecting themselves
- Registering themselves
- Performing failover
- Choosing alternate providers
- Managing application configuration

---

# Manager Responsibilities

Managers are responsible for:

- Provider registration
- Provider lookup
- Active provider selection
- Lifecycle management
- Initialization
- Shutdown
- Health monitoring
- Future failover support

Managers act as the orchestration layer between the application and providers.

---

# Benefits

Centralized provider selection provides:

- Separation of concerns
- Reduced code duplication
- Easier provider replacement
- Cleaner dependency management
- Simpler testing
- Future support for automatic failover
- Runtime provider switching

---

# Alternatives Considered

## Providers Selecting Themselves

Each provider would determine when it should be used.

**Rejected because:**

- Violates Single Responsibility Principle
- Requires providers to know about competing providers
- Introduces unnecessary coupling
- Complicates testing

---

## Application-Level Selection

Every application component would decide which provider to use.

**Rejected because:**

- Duplicated logic
- Tight coupling
- Difficult maintenance
- Inconsistent behavior

---

## Dependency Injection Container

A DI framework would resolve providers automatically.

**Rejected because:**

- Additional complexity
- Unnecessary dependency
- Limited benefit for the current architecture

---

# Consequences

Positive:

- Centralized orchestration
- Consistent provider lifecycle
- Improved extensibility
- Easier runtime configuration
- Simplified testing

Negative:

- Managers become responsible for additional orchestration logic
- Slight increase in abstraction

These trade-offs are acceptable because they improve maintainability and scalability.

---

# Future Enhancements

The manager architecture enables future capabilities such as:

- Automatic failover
- Load balancing
- Provider priority lists
- Runtime provider switching
- Capability-based provider selection
- Health-based routing
- Cost-aware provider selection

These features can be implemented without modifying provider implementations.

---

# Related Principles

This decision reinforces:

- Single Responsibility Principle
- Dependency Inversion Principle
- Open/Closed Principle
- Strategy Pattern
- Composition over Inheritance

---

# References

- `docs/architecture/components.md`
- `docs/architecture/overview.md`
- `docs/modules/voice.md`
- `docs/modules/llm.md`
- `docs/modules/memory.md`
- `docs/decisions/ADR-0001-provider-pattern.md`
```
