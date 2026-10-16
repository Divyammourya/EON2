# Coding Guide

## Purpose

This document defines the coding standards and engineering practices used throughout the EON codebase.

Following a consistent style improves readability, maintainability, and collaboration across the project.

---

# Supported Environment

Current development targets:

- Python 3.12+
- UTF-8 source files
- Type hints throughout the codebase

---

# General Principles

Write code that is:

- Simple
- Explicit
- Readable
- Modular
- Reusable
- Predictable

Avoid unnecessary abstraction and premature optimization.

---

# Design Principles

The codebase follows:

- SOLID Principles
- DRY (Don't Repeat Yourself)
- KISS (Keep It Simple)
- YAGNI (You Aren't Gonna Need It)
- Composition over Inheritance
- Dependency Inversion
- Explicit Resource Ownership

---

# Project Structure

Every module should follow a consistent structure.

Example:

```text
module/
├── __init__.py
├── manager.py
├── models.py
├── exceptions.py
├── providers/
├── utils.py
└── tests/
```

Each file should have a clearly defined responsibility.

---

# Naming Conventions

## Classes

Use PascalCase.

Examples:

```python
VoiceManager
MemoryStore
OpenAIProvider
```

---

## Functions and Methods

Use snake_case.

Examples:

```python
start_session()
health_check()
transcribe_audio()
```

---

## Variables

Use descriptive snake_case names.

Good:

```python
session_id
provider_name
audio_bytes
```

Avoid abbreviations unless they are universally understood.

---

## Constants

Use UPPER_SNAKE_CASE.

Example:

```python
DEFAULT_TIMEOUT
MAX_RETRIES
_AUDIO_METADATA_KEY
```

---

## Private Members

Prefix internal members with a single underscore.

Example:

```python
_client
_voice
_load_lock
```

---

# Type Hints

All public APIs must include type hints.

Example:

```python
def transcribe(
    session: VoiceSession,
) -> SpeechRecognitionResult:
```

Avoid untyped public interfaces.

---

# Docstrings

Public modules, classes, methods, and functions must include docstrings.

Use the Google-style format adopted throughout the project.

Document:

- Purpose
- Arguments
- Return values
- Raised exceptions

Private helpers should also be documented when their behavior is non-trivial.

---

# Error Handling

Never expose third-party exceptions outside their implementation layer.

Instead:

- Catch SDK exceptions
- Translate them into project-defined exceptions
- Preserve the original exception using `raise ... from ...`

Example:

```python
try:
    ...
except Exception as exc:
    raise VoiceInitializationError(...) from exc
```

---

# Interfaces

Application code should depend on abstract interfaces rather than concrete implementations.

Concrete providers should be replaceable without modifying application logic.

---

# Thread Safety

When shared mutable state exists:

- Protect it with locks.
- Keep critical sections as small as possible.
- Avoid unnecessary contention.

Shared state should never be modified without synchronization.

---

# Validation

Validate external input as early as possible.

Fail fast with clear exceptions when input is invalid.

Do not silently ignore invalid data.

---

# Logging

Logging should be:

- Informative
- Structured
- Consistent

Do not log:

- API keys
- Passwords
- Tokens
- Sensitive user data

---

# Imports

Organize imports in the following order:

1. Standard library
2. Third-party libraries
3. Project imports

Separate each group with a blank line.

---

# Testing Expectations

New functionality should include corresponding tests.

At a minimum:

- Unit tests
- Error handling tests
- Edge case tests

Critical infrastructure should also include integration tests.

---

# Documentation

When changing architecture or behavior, update the relevant documentation.

Documentation should remain synchronized with the implementation.

---

# Code Review Checklist

Before submitting code, verify that:

- Type hints are complete.
- Public APIs are documented.
- Tests pass.
- Exceptions are translated correctly.
- Naming conventions are followed.
- No dead code remains.
- No debugging statements remain.
- Documentation has been updated where necessary.

---

# Related Documentation

- `docs/guides/testing.md`
- `docs/guides/contributing.md`
- `docs/DESIGN_PRINCIPLES.md`
- `docs/NAMING.md`
- `docs/architecture/overview.md`
```
