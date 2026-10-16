# Dependencies

## Purpose

This document lists the external dependencies used throughout EON, their purpose, and the principles governing dependency selection.

Dependencies should be introduced deliberately, documented, and reviewed regularly to minimize unnecessary complexity and long-term maintenance costs.

---

# Dependency Philosophy

EON follows these principles when selecting dependencies:

- Prefer the Python standard library whenever practical.
- Introduce third-party packages only when they provide significant value.
- Keep the dependency graph small.
- Prefer actively maintained projects.
- Prefer widely adopted libraries with stable APIs.
- Avoid unnecessary transitive dependencies.
- Document every production dependency.

---

# Core Runtime Dependencies

## Python

Purpose:

The primary programming language used throughout EON.

Requirements:

- Python 3.12 or newer

---

## OpenAI SDK

Package:

```text
openai
```

Purpose:

- Large Language Models
- Speech Recognition
- Speech Synthesis

Used by:

- LLM Module
- Voice Module

---

## Piper

Package:

```text
piper-tts
```

Purpose:

Offline text-to-speech synthesis.

Used by:

- Voice Module

---

## Faster-Whisper

Package:

```text
faster-whisper
```

Purpose:

Offline speech recognition.

Used by:

- Voice Module

---

# Planned Dependencies

The following dependencies may be introduced in future development phases.

---

## Vector Database

Purpose:

Long-term semantic memory.

Possible candidates:

- ChromaDB
- FAISS
- Qdrant
- Milvus

Status:

Planned

---

## Database

Purpose:

Persistent application storage.

Possible candidates:

- SQLite
- PostgreSQL

Status:

Planned

---

## Configuration

Purpose:

Configuration validation and serialization.

Possible candidates:

- Pydantic

Status:

Under evaluation

---

## Plugin Support

Purpose:

Dynamic plugin discovery and loading.

Likely implementation:

Python standard library (`importlib`)

Status:

Planned

---

# Development Dependencies

These dependencies are intended only for development and are not required at runtime.

Examples include:

- Formatter
- Linter
- Type checker
- Test framework
- Coverage tools

Specific packages will be documented as they are adopted.

---

# Dependency Categories

Dependencies fall into the following categories:

| Category | Description |
|----------|-------------|
| Runtime | Required for normal application execution |
| Development | Used during development only |
| Testing | Used exclusively for testing |
| Documentation | Used to build or maintain documentation |
| Tooling | Used for formatting, linting, or static analysis |

---

# Dependency Review

Before adding a new dependency, consider:

- Can the standard library solve the problem?
- Is the package actively maintained?
- Is the API stable?
- Does it introduce unnecessary transitive dependencies?
- Does it align with the project's architecture?
- Is the maintenance cost justified?

Dependencies should be reviewed periodically to remove obsolete or unused packages.

---

# Version Management

General guidelines:

- Prefer stable releases.
- Pin versions where reproducibility is important.
- Upgrade dependencies regularly.
- Review release notes before major upgrades.
- Test thoroughly after upgrades.

---

# Security

All dependencies should be monitored for:

- Security vulnerabilities
- License compatibility
- Maintenance status
- Breaking changes

Outdated or unmaintained dependencies should be replaced when practical.

---

# Future Dependency Policy

As EON grows:

- Runtime dependencies should remain minimal.
- Optional features should avoid forcing unnecessary dependencies.
- Provider implementations should isolate vendor-specific SDKs behind interfaces.
- Dependency injection should minimize coupling to third-party libraries.

---

# Related Documentation

- `PROJECT.md`
- `DESIGN_PRINCIPLES.md`
- `architecture/overview.md`
- `architecture/components.md`
- `ROADMAP.md`
