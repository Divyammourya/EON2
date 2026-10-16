# Roadmap

## Purpose

This document outlines the planned evolution of EON.

The roadmap is organized into development phases rather than fixed release dates. As implementation progresses, phases may be expanded, reordered, or refined.

---

# Guiding Principles

Development priorities are driven by:

- Architectural stability
- Incremental feature delivery
- Maintainability
- Comprehensive documentation
- High test coverage
- Long-term extensibility

Features should only be implemented after their architecture has been designed and documented.

---

# Phase 1 — Foundation ✅

## Objectives

Establish the project's architectural and engineering foundations.

### Completed

- Repository structure
- Documentation structure
- Clean Architecture foundation
- SOLID-oriented design
- Provider abstractions
- Voice module
- OpenAI speech provider
- Piper speech provider
- Faster-Whisper provider
- Session lifecycle
- Architecture documentation
- Module documentation
- Architecture Decision Records
- Developer guides

---

# Phase 2 — LLM Module

## Objectives

Build the core language model subsystem.

### Planned

- LLM interfaces
- Provider abstraction
- OpenAI provider
- Conversation management
- Prompt management
- Streaming responses
- Token accounting
- Model configuration
- Provider registry
- Error handling
- Unit tests

---

# Phase 3 — Memory Module

## Objectives

Implement conversational memory and contextual retrieval.

### Planned

- Memory interfaces
- Short-term memory
- Long-term memory
- Context retrieval
- Conversation history
- Memory persistence
- Embedding support
- Retrieval strategies
- Memory tests

---

# Phase 4 — Plugin System

## Objectives

Create an extensible plugin architecture.

### Planned

- Plugin interfaces
- Plugin loader
- Plugin registry
- Tool discovery
- Lifecycle management
- Dependency validation
- Configuration support
- Security boundaries
- Plugin testing

---

# Phase 5 — Storage Layer

## Objectives

Provide persistent storage abstractions.

### Planned

- Storage interfaces
- Configuration storage
- Session persistence
- Memory persistence
- Database providers
- File providers
- Migration support
- Backup support

---

# Phase 6 — Orchestration

## Objectives

Connect all modules into a unified runtime.

### Planned

- Application lifecycle
- Dependency injection
- Module initialization
- Provider selection
- Configuration loading
- Service registry
- Runtime coordination

---

# Phase 7 — Intelligence

## Objectives

Expand EON's reasoning capabilities.

### Planned

- Tool calling
- Multi-step reasoning
- Context planning
- Memory integration
- Decision orchestration
- Agent workflows

---

# Phase 8 — Automation

## Objectives

Enable autonomous task execution.

### Planned

- Scheduler
- Background jobs
- Event system
- Notifications
- Workflow execution
- Trigger-based automation

---

# Phase 9 — User Interfaces

## Objectives

Provide interfaces for interacting with EON.

### Planned

- Command-line interface
- Desktop application
- Web interface
- REST API
- Python SDK
- Remote management

---

# Phase 10 — Ecosystem

## Objectives

Expand EON into a broader platform.

### Planned

- Community plugins
- Marketplace
- Public APIs
- External integrations
- Developer tooling
- Documentation website

---

# Ongoing Work

The following activities continue throughout every phase:

- Refactoring
- Documentation updates
- Testing
- Performance improvements
- Dependency updates
- Bug fixes
- Architecture reviews
- ADR creation

---

# Release Philosophy

EON follows an architecture-first development process.

Every major feature should progress through the following lifecycle:

1. Requirements
2. Architecture
3. ADR (if required)
4. Implementation
5. Testing
6. Documentation
7. Release

---

# Long-Term Vision

Future versions of EON aim to provide:

- Advanced conversational intelligence
- Persistent long-term memory
- Multi-provider AI orchestration
- Rich plugin ecosystem
- Autonomous workflows
- Scalable architecture
- Excellent developer experience

---

# Related Documentation

- `PROJECT.md`
- `VISION.md`
- `STATUS.md`
- `CHANGELOG.md`
- `architecture/overview.md`
- `decisions/README.md`
