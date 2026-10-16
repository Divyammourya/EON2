# Contributing Guide

## Purpose

This document defines the contribution workflow for the EON project.

Every contribution, whether it is a bug fix, feature, documentation update, refactor, or architectural improvement, should follow the same development process to maintain consistency and code quality.

---

# Before Contributing

Before writing code:

- Understand the problem.
- Review the existing architecture.
- Read the relevant ADRs.
- Check for existing issues or planned work.
- Ensure the proposed change aligns with the project's design principles.

---

# Development Workflow

The recommended workflow is:

1. Create or select an issue.
2. Create a new Git branch.
3. Implement the change.
4. Add or update tests.
5. Update documentation.
6. Run all quality checks.
7. Submit a Pull Request.
8. Address review feedback.
9. Merge after approval.

Every change should be small, focused, and easy to review.

---

# Branch Naming

Use descriptive branch names.

Examples:

```text
feature/voice-manager
feature/openai-provider
feature/memory-storage

fix/session-registration
fix/transcription-timeout

refactor/provider-interface

docs/architecture-update

test/voice-module
```

---

# Pull Requests

Each Pull Request should focus on a single logical change.

A Pull Request should include:

- A clear description
- Motivation for the change
- Testing performed
- Documentation updates
- Any architectural implications

Avoid combining unrelated changes into the same Pull Request.

---

# Code Review Expectations

During review, verify that:

- The implementation follows project architecture.
- Naming conventions are respected.
- Type hints are complete.
- Public APIs are documented.
- Error handling is appropriate.
- Tests cover new behavior.
- Documentation has been updated.
- No unnecessary complexity has been introduced.

Constructive feedback should focus on improving the project rather than personal preferences.

---

# Documentation Requirements

Documentation is part of the implementation.

When introducing significant changes, update the relevant documents, including:

- Architecture documentation
- ADRs
- Module documentation
- Developer guides
- Project documentation

Documentation should accurately reflect the current state of the codebase.

---

# Testing Requirements

Before submitting changes:

- Run the full test suite.
- Ensure new tests pass.
- Verify existing tests still pass.
- Add tests for new functionality.
- Update tests if behavior changes.

Code without appropriate tests should not be considered complete.

---

# Coding Standards

All contributions should follow the project's coding standards.

This includes:

- Type hints
- Google-style docstrings
- Consistent naming
- SOLID principles
- Proper exception handling
- Modular design

Refer to `docs/guides/coding.md` for detailed standards.

---

# Commit Quality

Each commit should represent a logical unit of work.

Good commits:

- Are focused
- Build successfully
- Keep the project in a working state
- Have descriptive commit messages

Avoid commits that mix unrelated changes.

---

# Backward Compatibility

When modifying public interfaces:

- Preserve backward compatibility whenever practical.
- Clearly document breaking changes.
- Update dependent components.
- Record major architectural changes using an ADR.

---

# Security

Contributors should never commit:

- API keys
- Passwords
- Tokens
- Secrets
- Private credentials
- Personal data

Sensitive information should be provided through secure configuration mechanisms.

---

# Performance

When introducing new features:

- Consider memory usage.
- Consider CPU usage.
- Avoid unnecessary allocations.
- Avoid premature optimization.
- Measure performance before optimizing.

Readability should generally take priority unless performance is a demonstrated concern.

---

# Communication

When discussing changes:

- Be respectful.
- Be constructive.
- Explain technical reasoning.
- Reference documentation when appropriate.
- Focus on improving the project.

Healthy technical discussion is encouraged.

---

# Contribution Checklist

Before opening a Pull Request, verify that:

- The code builds successfully.
- All tests pass.
- New functionality is tested.
- Documentation is updated.
- Naming conventions are followed.
- Public APIs are documented.
- No debugging code remains.
- No unused imports remain.
- No dead code remains.
- Changes align with the project's architecture.

---

# Related Documentation

- `docs/guides/coding.md`
- `docs/guides/testing.md`
- `docs/guides/git.md`
- `docs/architecture/README.md`
- `docs/decisions/README.md`
- `docs/PROJECT.md`
```
