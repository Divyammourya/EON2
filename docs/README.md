# EON Documentation

Welcome to the official documentation for **EON**.

This documentation describes the architecture, engineering decisions, development practices, modules, roadmap, and long-term vision of the project.

The documentation is intended for contributors, maintainers, and anyone interested in understanding how EON is designed and developed.

---

# Documentation Structure

## Architecture

Describes the overall system design and technical architecture.

```
architecture/
```

Includes:

- System overview
- Component architecture
- Voice architecture
- Memory architecture
- LLM architecture
- Plugin architecture
- Storage architecture
- Directory structure
- System diagrams

---

## Modules

Describes each major module within EON.

```
modules/
```

Includes:

- Voice
- Memory
- LLM

---

## Architecture Decision Records (ADRs)

Documents significant architectural decisions and the reasoning behind them.

```
decisions/
```

Includes:

- Provider pattern
- Session lifecycle
- Provider selection
- Memory architecture
- Plugin system

---

## Developer Guides

Defines development workflows and engineering standards.

```
guides/
```

Includes:

- Coding standards
- Testing practices
- Contribution workflow
- Git workflow

---

# Project Documentation

The root of the `docs` directory contains project-wide documentation.

| Document | Purpose |
|----------|---------|
| `PROJECT.md` | High-level overview of EON |
| `VISION.md` | Long-term vision and goals |
| `ROADMAP.md` | Planned development milestones |
| `STATUS.md` | Current project status |
| `CHANGELOG.md` | History of significant changes |
| `DEPENDENCIES.md` | External dependencies |
| `NAMING.md` | Naming conventions |
| `DESIGN_PRINCIPLES.md` | Core engineering principles |
| `DEVELOPMENT_LOG.md` | Development history |
| `IDEAS.md` | Future ideas and experiments |
| `FUTURE_ARCHITECTURE.md` | Planned architectural evolution |
| `CHAT_CONTEXT.md` | AI collaboration context |
| `AI_GUIDE.md` | Guidelines for AI-assisted development |

---

# Reading Order

For new contributors, the recommended reading order is:

1. `PROJECT.md`
2. `VISION.md`
3. `architecture/overview.md`
4. `architecture/components.md`
5. `architecture/system_diagrams.md`
6. `modules/README.md`
7. `decisions/README.md`
8. `guides/README.md`
9. `ROADMAP.md`
10. `STATUS.md`

This sequence provides a complete understanding of the project before contributing.

---

# Documentation Principles

The EON documentation follows these principles:

- Documentation is part of the implementation.
- Architecture is documented before implementation.
- Every significant architectural decision is recorded.
- Documentation evolves with the codebase.
- Public APIs are documented.
- Technical debt is documented rather than hidden.

---

# Contributing

When making changes to EON:

- Update relevant documentation.
- Keep architecture diagrams current.
- Record major architectural decisions as ADRs.
- Ensure documentation reflects the current implementation.

---

# Project Philosophy

EON emphasizes:

- Clean Architecture
- SOLID principles
- Dependency Inversion
- Modular design
- Extensibility
- Strong typing
- Comprehensive documentation
- Long-term maintainability

These principles guide every architectural and engineering decision within the project.
