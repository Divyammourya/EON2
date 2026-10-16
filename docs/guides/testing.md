# Testing Guide

## Purpose

This document defines the testing philosophy, standards, and practices used throughout the EON project.

Testing is treated as a core part of development rather than an optional activity. Every feature should be accompanied by tests that verify correctness, reliability, and long-term maintainability.

---

# Testing Philosophy

EON follows these principles:

- Test behavior, not implementation.
- Write deterministic tests.
- Keep tests isolated.
- Prefer small unit tests.
- Cover both success and failure paths.
- Automate testing whenever possible.

A feature is not considered complete until it has appropriate test coverage.

---

# Testing Pyramid

Testing should follow the traditional testing pyramid.

```text
                End-to-End
             ───────────────
             Integration Tests
         ─────────────────────────
              Unit Tests
────────────────────────────────────────
```

The majority of tests should be unit tests.

---

# Test Types

## Unit Tests

Unit tests verify a single class or function in isolation.

Characteristics:

- Fast
- Independent
- No external services
- Highly repeatable

Examples:

- Utility functions
- Validation logic
- Exception translation
- Provider behavior
- Session lifecycle

---

## Integration Tests

Integration tests verify interactions between multiple components.

Examples:

- Manager ↔ Provider
- Memory ↔ Storage
- LLM ↔ Provider
- Voice ↔ Provider

These tests ensure components work correctly together.

---

## End-to-End Tests

End-to-end tests verify complete user workflows.

Examples:

- Voice input → transcription → LLM → speech output
- Memory retrieval during a conversation
- Plugin execution through the application

These tests are fewer in number due to their higher cost and complexity.

---

# Test Organization

Tests should mirror the project structure.

Example:

```text
src/
└── modules/
    └── voice/
        ├── manager.py
        ├── providers/
        └── ...

tests/
└── modules/
    └── voice/
        ├── test_manager.py
        ├── test_piper_provider.py
        ├── test_openai_provider.py
        └── ...
```

This makes tests easy to locate and maintain.

---

# Naming Conventions

Test files:

```text
test_<module>.py
```

Examples:

```text
test_manager.py
test_models.py
test_exceptions.py
test_openai_provider.py
```

Test functions should describe expected behavior.

Example:

```python
def test_start_session_registers_session():
    ...

def test_transcribe_requires_active_session():
    ...

def test_invalid_voice_id_raises_error():
    ...
```

---

# Mocking

External dependencies should be mocked.

Examples include:

- OpenAI API
- Databases
- File system
- Network requests
- Third-party SDKs

Unit tests should not rely on internet access or external services.

---

# Exception Testing

Every custom exception path should have corresponding tests.

Verify:

- Correct exception type
- Error message
- Attached details
- Exception chaining

Example:

```python
with pytest.raises(VoiceInitializationError):
    provider.initialize()
```

---

# Edge Cases

Tests should include edge cases such as:

- Empty input
- Invalid arguments
- Missing configuration
- Unsupported operations
- Boundary values
- Concurrent access
- Resource cleanup

Edge case testing improves robustness.

---

# Thread Safety Testing

Components that use synchronization primitives should include tests for concurrent behavior.

Examples:

- Lazy initialization
- Session registration
- Shared provider state
- Lock-protected resources

Concurrency bugs should be detected as early as possible.

---

# Test Coverage

Aim for high coverage of business logic.

Prioritize testing:

- Public APIs
- Validation
- Exception handling
- State transitions
- Critical workflows

Coverage percentage is a useful metric but should never replace meaningful test design.

---

# Continuous Integration

Every change should pass the full test suite before being merged.

The CI pipeline should include:

- Static analysis
- Formatting checks
- Type checking
- Unit tests
- Integration tests

Build failures should block merges until resolved.

---

# Test Maintenance

Tests should evolve with the codebase.

When modifying behavior:

- Update existing tests.
- Remove obsolete tests.
- Add tests for new functionality.

Tests should remain readable and maintainable.

---

# Related Documentation

- `docs/guides/coding.md`
- `docs/guides/contributing.md`
- `docs/architecture/overview.md`
- `docs/PROJECT.md`
