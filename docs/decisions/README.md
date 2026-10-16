# Architecture Decision Records (ADRs)

## Purpose

This directory contains the Architecture Decision Records (ADRs) for EON.

An Architecture Decision Record captures an important architectural decision, the reasoning behind it, the alternatives that were considered, and the consequences of choosing a particular solution.

Unlike the architecture documentation, which describes **how the system is structured**, ADRs explain **why it was designed that way**.

---

# What is an ADR?

An ADR is a short document that records:

- The problem being solved
- The architectural decision
- Alternative solutions
- Trade-offs
- Consequences

Every significant architectural decision should be documented as an ADR.

---

# ADR Lifecycle

An ADR progresses through one of the following states:

| Status | Meaning |
|---------|---------|
| Proposed | Under discussion |
| Accepted | Approved and implemented |
| Superseded | Replaced by a newer ADR |
| Deprecated | No longer recommended |
| Rejected | Considered but not adopted |

---

# Naming Convention

Each ADR uses the following format:

```
ADR-XXXX-short-description.md
```

Examples:

```
ADR-0001-provider-pattern.md
ADR-0002-session-lifecycle.md
ADR-0003-provider-selection.md
```

Numbers are never reused.

If an ADR is replaced, the old ADR remains in the repository for historical reference.

---

# Current ADRs

## ADR-0001 — Provider Pattern

Explains why external libraries are isolated behind provider abstractions.

---

## ADR-0002 — Session Lifecycle

Documents the decision to introduce explicit session management for stateful modules.

---

## ADR-0003 — Provider Selection

Explains why provider selection is centralized rather than delegated to individual providers.

---

## ADR-0004 — Memory Architecture

Documents the planned memory subsystem and its separation from the LLM module.

---

## ADR-0005 — Plugin System

Explains the decision to implement an extensible plugin architecture using interfaces and lifecycle management.

---

# ADR Template

Every ADR should follow this structure:

```text
Title

Status

Context

Decision

Alternatives Considered

Consequences

References
```

Keeping ADRs consistent makes architectural history easier to understand.

---

# When to Create a New ADR

Create a new ADR when:

- Introducing a new architectural pattern
- Replacing an existing architecture
- Adding a major subsystem
- Changing dependency direction
- Introducing a new external technology
- Making a long-term design decision

Do not create ADRs for minor implementation details.

---

# Relationship to Other Documentation

The architecture documentation explains:

> What the system looks like.

The ADRs explain:

> Why the system was designed that way.

Both are necessary to understand and maintain EON over time.

---

# Related Documents

- ../architecture/overview.md
- ../architecture/components.md
- ../architecture/system_diagrams.md
- ../PROJECT.md
- ../VISION.md
