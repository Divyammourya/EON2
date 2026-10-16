# Directory Structure

## Purpose

This document describes the organization of the EON source tree and the responsibilities of each major directory.

---

# Repository Layout

```text
EON/
├── docs/
├── src/
├── tests/
├── scripts/
├── assets/
├── config/
└── pyproject.toml
```

---

# docs/

Contains all project documentation.

Responsibilities:

- Architecture documentation
- Module documentation
- Development guides
- Decision records
- Project planning
- Roadmaps
- Changelogs

Documentation should remain synchronized with the implementation.

---

# src/

Contains the application's source code.

All production code resides within this directory.

Organized primarily by feature rather than by technical layer.

---

# src/core/

Contains application-wide infrastructure shared across modules.

Examples include:

- Configuration
- Logging
- Dependency Injection
- Utilities
- Shared abstractions

Business logic should not reside here.

---

# src/modules/

Contains all feature modules.

Each module owns its own implementation and exposes a public interface.

Modules should remain as independent as possible.

Current modules include:

- Voice
- Memory (planned)
- LLM (planned)

---

# Module Layout

Each module follows a consistent internal structure.

```text
module/
├── exceptions.py
├── models.py
├── services.py
├── providers/
├── interfaces/
└── __init__.py
```

Not every module will require every directory, but consistency should be maintained whenever practical.

---

# src/modules/voice/

Implements speech recognition and speech synthesis.

Responsibilities include:

- Voice providers
- Voice models
- Session management
- Speech recognition
- Speech synthesis
- Voice exceptions

---

# src/modules/memory/

Status

Planned

Will manage conversational memory and persistent knowledge.

---

# src/modules/llm/

Status

Planned

Will provide language model abstractions and provider implementations.

---

# tests/

Contains automated tests.

Tests mirror the structure of the source tree.

Example

```text
tests/
└── modules/
    └── voice/
```

Testing code should never be mixed with production code.

---

# scripts/

Contains utility scripts used during development.

Examples include:

- Build scripts
- Development utilities
- Migration scripts
- Automation tools

Scripts should not contain application business logic.

---

# assets/

Contains static project assets.

Examples include:

- Images
- Audio
- Icons
- Sample files
- Models (if appropriate)

---

# config/

Contains project configuration files.

Examples include:

- Default configuration
- Templates
- Environment examples

Sensitive configuration should never be committed.

---

# Provider Organization

Provider implementations are grouped together.

Example

```text
providers/
├── openai.py
├── piper.py
├── faster_whisper.py
```

Each provider implements one or more provider interfaces.

---

# Documentation Organization

Documentation is organized separately from implementation.

```text
docs/
├── architecture/
├── modules/
├── guides/
└── decisions/
```

This separation keeps implementation and documentation independently maintainable.

---

# Naming Conventions

Directories use:

- lowercase
- descriptive names
- singular nouns where appropriate

Examples

Good

```text
voice
memory
providers
services
```

Avoid

```text
VoiceModule
VOICE
misc
helpers
```

---

# Architectural Rules

The directory structure reflects architectural boundaries.

Rules include:

- Modules own their implementation.
- Infrastructure is shared.
- Providers isolate third-party libraries.
- Documentation lives outside source code.
- Tests mirror production code.
- Feature organization is preferred over technical organization.

---

# Future Expansion

The structure is designed to accommodate additional modules without major reorganization.

Examples include:

- vision/
- planning/
- plugins/
- automation/
- workflows/

New modules should follow the established organizational conventions.

---

# Related Documents

- overview.md
- components.md
- voice.md
- ../modules/README.md
