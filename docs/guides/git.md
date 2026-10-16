# Git Guide

## Purpose

This document defines the Git workflow used throughout the EON project.

A consistent Git workflow improves collaboration, simplifies code reviews, and maintains a clean project history.

---

# Branch Strategy

The project follows a feature branch workflow.

The `main` branch always represents the stable version of the project.

Development work should be performed in separate branches and merged only after review.

---

# Branch Naming

Use lowercase branch names with descriptive prefixes.

## Feature

```text
feature/voice-manager
feature/openai-provider
feature/memory-system
feature/plugin-loader
```

## Bug Fix

```text
fix/session-registration
fix/audio-loading
fix/provider-selection
```

## Refactor

```text
refactor/provider-interface
refactor/voice-manager
```

## Documentation

```text
docs/architecture
docs/testing-guide
docs/readme-update
```

## Testing

```text
test/voice-module
test/memory-module
```

---

# Commit Messages

Write commit messages in the imperative mood.

Examples:

```text
Add OpenAI voice provider
Implement provider registry
Refactor session lifecycle
Fix audio validation bug
Update architecture documentation
```

Avoid vague messages such as:

```text
Update
Changes
Fix stuff
Misc
```

Each commit should represent a single logical change.

---

# Commit Frequency

Commit regularly during development.

Small, focused commits are preferred over large, unrelated changes.

Each commit should leave the project in a buildable and testable state.

---

# Pull Requests

Before opening a Pull Request:

- Ensure all tests pass.
- Update documentation if needed.
- Remove debugging code.
- Verify formatting and type hints.
- Review the changes locally.

Each Pull Request should address one feature or issue.

---

# Merging

Use merge strategies that preserve a clear project history.

Before merging:

- Resolve conflicts.
- Rebase or merge from the latest `main` if necessary.
- Confirm CI checks pass.
- Ensure the Pull Request has been reviewed.

Do not merge code with failing tests or unresolved review comments.

---

# Releases

Stable releases should be identified using semantic versioning.

Format:

```text
MAJOR.MINOR.PATCH
```

Examples:

```text
1.0.0
1.1.0
1.1.1
2.0.0
```

Guidelines:

- Increment **MAJOR** for breaking changes.
- Increment **MINOR** for new backward-compatible features.
- Increment **PATCH** for backward-compatible bug fixes.

---

# Tags

Create Git tags for released versions.

Examples:

```text
v0.1.0
v0.5.0
v1.0.0
```

Tags provide stable reference points for releases.

---

# Keeping Branches Updated

Before merging:

1. Fetch the latest changes.
2. Update your branch with the latest `main`.
3. Resolve any conflicts.
4. Run the test suite again.

Keeping branches current reduces integration issues.

---

# Repository Hygiene

Avoid committing:

- Generated files
- Build artifacts
- Temporary files
- Virtual environments
- Secrets
- API keys
- Local configuration files

Ensure `.gitignore` is kept up to date.

---

# Recommended Workflow

```text
Create Issue
      │
      ▼
Create Branch
      │
      ▼
Implement Feature
      │
      ▼
Write Tests
      │
      ▼
Update Documentation
      │
      ▼
Run Quality Checks
      │
      ▼
Open Pull Request
      │
      ▼
Code Review
      │
      ▼
Merge into main
      │
      ▼
Tag Release (when applicable)
```

---

# Related Documentation

- `docs/guides/README.md`
- `docs/guides/coding.md`
- `docs/guides/testing.md`
- `docs/guides/contributing.md`
- `docs/CHANGELOG.md`
- `docs/ROADMAP.md`
