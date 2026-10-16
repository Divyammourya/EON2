# Changelog

All notable changes to EON are documented in this file.

The project follows the principles of Keep a Changelog while using development phases instead of semantic versioning during early development.

---

# Unreleased

## Added

### Identity Module

Implemented EON's identity system.

Features include:

- IdentityProfile
- IdentityManager
- Dynamic system prompt generation
- Creator information
- Capability management
- Personality definition

---

### Memory Module

Major improvements to the semantic memory system.

Features include:

- SQLite memory storage
- Embedding generation
- Cosine similarity search
- Duplicate memory detection
- Long-term memory retrieval
- Recall pipeline
- Store pipeline

---

### Context Module

Implemented contextual understanding.

Features include:

- Conversation context
- Relevant memory injection
- Identity-aware prompts

---

### Perception Module

Added user message perception.

Features include:

- Conversation perception
- Context preparation
- Foundation for entity extraction

---

### Recall Module

Implemented semantic memory retrieval.

Features include:

- Memory querying
- Similarity ranking
- Relevant memory selection
- Recall service

---

### Store Module

Implemented long-term memory storage decisions.

Features include:

- Duplicate checking
- Embedding generation
- Store decision pipeline
- Memory persistence

---

### Tools Module

Introduced the first production-ready tool architecture.

Features include:

- Tool abstraction
- LauncherTool
- Tool registry
- Cached application discovery
- Desktop application launcher

---

### Launcher

Improved desktop application discovery.

Features include:

- Application cache
- Faster startup
- Start Menu discovery
- Executable discovery
- Alias support

---

### Architecture

Improved overall runtime architecture.

Changes include:

- Identity-aware Brain
- Dynamic system prompts
- Semantic memory pipeline
- Cached launcher architecture
- Improved dependency injection
- Better module separation

---

## Improved

- Faster startup using cached application registry.
- Improved semantic memory retrieval.
- Better duplicate memory detection.
- Cleaner Brain architecture.
- Dynamic identity instead of hardcoded prompts.
- Improved launcher performance.

---

# Phase 1 — Foundation

## Added

### Repository

- Standardized repository structure
- Organized documentation hierarchy
- Module-based architecture
- Documentation assets directory

### Architecture

- Overall system architecture
- Voice architecture
- Memory architecture
- LLM architecture
- Plugin architecture
- Storage architecture
- System component documentation
- Directory structure documentation
- Architecture diagrams documentation

### Voice Module

Implemented the first production-ready module.

Features include:

- Provider abstraction
- Session lifecycle
- Speech synthesis interface
- Speech recognition interface
- OpenAI provider
- Piper provider
- Faster-Whisper provider
- Custom exception hierarchy
- Request models
- Response models
- Session models

### Design

Documented architectural decisions for:

- Provider pattern
- Session lifecycle
- Provider selection
- Memory architecture
- Plugin system

### Developer Documentation

Added:

- Coding standards
- Testing guide
- Git workflow
- Contribution guide

### Project Documentation

Created:

- Project overview
- Vision
- Roadmap
- Status tracking
- Naming conventions
- Design principles
- Development log
- AI guide
- Chat context
- Future architecture planning

---

# Future Releases

## Phase 2

- Complete LLM module
- Conversation management
- Streaming support

## Phase 3

- Advanced semantic memory
- Vector database abstraction
- Context management

## Phase 4

- Plugin framework
- Dynamic tool loading
- Permission system

## Phase 5

- Storage subsystem
- Session persistence
- Configuration persistence

## Phase 6

- Runtime orchestration
- Event bus
- Dependency injection improvements

## Phase 7

- Desktop UI
- CLI
- API
- Web interface

## Phase 8

- Testing
- CI/CD
- Performance optimization
- Documentation completion

---

# Versioning Strategy

Development is tracked by project phases until the first public release.

Planned progression:

- Phase 1 → 0.1.0
- Phase 2 → 0.2.0
- Phase 3 → 0.3.0
- Phase 4 → 0.4.0
- Phase 5 → 0.5.0
- Phase 6 → 0.6.0
- Phase 7 → 0.9.0
- Stable Release → 1.0.0

---

# Change Categories

- Added
- Changed
- Improved
- Deprecated
- Removed
- Fixed
- Planned

---

# Related Documentation

- PROJECT.md
- ROADMAP.md
- STATUS.md
- DEVELOPMENT_LOG.md
