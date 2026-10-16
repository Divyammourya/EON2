# Developer Guides

## Purpose

This directory contains the developer documentation for EON.

These guides define the engineering practices, workflows, coding standards, testing strategy, and contribution process used throughout the project.

Unlike the architecture documentation, which explains how the system is designed, these guides explain how developers should build and maintain it.

---

# Guide Index

## Coding Guide

**File**

```
coding.md
```

Describes:

- Python coding standards
- Naming conventions
- Documentation requirements
- Type hinting
- Exception handling
- Project structure
- Design principles

---

## Testing Guide

**File**

```
testing.md
```

Describes:

- Testing philosophy
- Unit testing
- Integration testing
- Mocking
- Test organization
- Coverage expectations
- Continuous testing

---

## Contributing Guide

**File**

```
contributing.md
```

Describes:

- Contribution workflow
- Pull request process
- Code review expectations
- Branch strategy
- Documentation updates
- Development requirements

---

## Git Guide

**File**

```
git.md
```

Describes:

- Branch naming
- Commit message conventions
- Merge strategy
- Release tagging
- Repository workflow

---

# Engineering Philosophy

EON prioritizes:

- Readability over cleverness
- Simplicity over unnecessary abstraction
- Explicit behavior over implicit behavior
- Maintainability over short-term convenience
- Consistency across the codebase
- Strong typing
- Comprehensive documentation
- Extensive testing

Every contribution should reinforce these principles.

---

# Core Development Principles

Developers should strive to produce code that is:

- Modular
- Testable
- Extensible
- Predictable
- Well documented
- Type safe
- Thread safe where applicable

The architecture should evolve without sacrificing clarity.

---

# Documentation Expectations

Code and documentation evolve together.

Whenever a significant architectural or behavioral change is introduced, the relevant documentation should be updated in the same change set.

This includes:

- Architecture documents
- ADRs
- Module documentation
- Developer guides
- Project documentation

Documentation is considered part of the implementation, not an optional follow-up task.

---

# Related Documentation

- `docs/architecture/README.md`
- `docs/decisions/README.md`
- `docs/modules/README.md`
- `docs/PROJECT.md`
- `docs/README.md`
