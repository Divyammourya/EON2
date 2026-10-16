# AI Guide

## Purpose

This document provides guidance for AI assistants (such as ChatGPT, Claude, Gemini, Copilot, or future coding assistants) that contribute to the EON codebase.

Its goal is to ensure that AI-generated code remains consistent with the project's architecture, coding standards, and long-term vision.

This document complements, but does not replace, the project's coding standards and architecture documentation.

---

# Project Overview

EON is a modular AI operating system designed with a strong emphasis on:

- Clean Architecture
- SOLID principles
- Dependency Inversion
- Provider-based design
- Extensibility
- Testability
- Long-term maintainability

AI-generated code should reinforce these principles rather than introduce shortcuts or architectural drift.

---

# Architecture Rules

When generating code:

- Respect existing module boundaries.
- Depend on abstractions, not concrete implementations.
- Never bypass provider interfaces.
- Avoid circular dependencies.
- Keep responsibilities clearly separated.
- Follow the documented architecture before introducing new patterns.

---

# Provider Pattern

External services must always be isolated behind provider abstractions.

Examples include:

- LLM providers
- Speech providers
- Memory providers
- Storage providers

Never access third-party SDKs directly outside their corresponding provider implementation.

---

# Code Quality

Generated code should be:

- Readable
- Explicit
- Type annotated
- Well documented
- Easy to test
- Consistent with existing naming conventions

Avoid overly clever or unnecessarily compact solutions.

---

# Documentation

Public modules, classes, and methods should include clear docstrings.

Major architectural changes should also update:

- Architecture documentation
- Module documentation
- ADRs (when applicable)
- Developer guides

Documentation should evolve alongside the code.

---

# Error Handling

AI-generated code should:

- Validate external input.
- Fail fast on invalid state.
- Translate third-party exceptions into project-specific exceptions.
- Avoid leaking implementation details across module boundaries.

---

# Thread Safety

When introducing shared mutable state:

- Use synchronization where necessary.
- Avoid unnecessary locking.
- Keep critical sections small.
- Prefer immutable data when possible.

Thread safety should be considered whenever providers or managers maintain shared state.

---

# Dependency Management

Before introducing a new dependency:

- Prefer the Python standard library.
- Justify the dependency.
- Ensure it aligns with project goals.
- Document it in `DEPENDENCIES.md`.

Do not introduce unnecessary packages.

---

# Testing Expectations

Generated code should be testable.

Design for:

- Unit testing
- Mocking
- Dependency injection
- Deterministic behavior

Avoid hidden global state or tightly coupled implementations.

---

# Naming

Follow the project's naming conventions:

- PascalCase for classes.
- snake_case for functions and variables.
- UPPER_SNAKE_CASE for constants.
- Descriptive names over abbreviations.

Refer to `NAMING.md` for details.

---

# Preferred Design Patterns

AI-generated code should favor:

- Strategy Pattern
- Provider Pattern
- Factory Pattern (where appropriate)
- Composition over inheritance
- Dependency Injection

Avoid introducing patterns that add complexity without clear benefit.

---

# Things to Avoid

Do **not**:

- Hardcode API keys or secrets.
- Duplicate existing functionality.
- Introduce hidden global state.
- Bypass abstraction layers.
- Create monolithic classes.
- Ignore documented architecture.
- Modify unrelated code unnecessarily.

Every change should have a clear purpose.

---

# Before Submitting Code

An AI assistant should verify:

- Does the implementation follow the architecture?
- Are responsibilities clearly separated?
- Are type hints complete?
- Are docstrings present?
- Are exceptions handled correctly?
- Are dependencies justified?
- Is the code easy to understand?
- Does it follow project naming conventions?

If the answer to any question is "no," the implementation should be revised.

---

# Long-Term Goal

AI should act as a collaborator that strengthens EON's architecture, not merely as a code generator.

The preferred solution is not the shortest one, but the one that best aligns with the project's design principles and long-term maintainability.

---

# Related Documentation

- `PROJECT.md`
- `DESIGN_PRINCIPLES.md`
- `NAMING.md`
- `DEPENDENCIES.md`
- `guides/coding.md`
- `architecture/overview.md`
- `decisions/README.md`
