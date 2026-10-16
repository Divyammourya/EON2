# EON Development Session Handoff

This document is intended for both human developers and AI assistants continuing development of EON.

Read this document before making architectural changes.

---

# Project Overview

EON is a modular, local-first AI operating system designed to function as a personal intelligent assistant.

Unlike a traditional chatbot, EON is built around independent modules responsible for understanding, planning, reasoning, execution, memory, and desktop interaction.

The long-term goal is to create an autonomous AI assistant capable of interacting naturally with both users and the local computer.

---

# Current Version

Version:

0.1.0

Development Phase:

Foundation Complete

Status:

Active Development

---

# Current Architecture

The current request pipeline is:

```text
User

↓

Conversation

↓

Perception

↓

Recall

↓

Context

↓

Brain

↓

Intent

↓

Planner

↓

Reasoning

↓

Execution

↓

Tools

↓

Response
```

Every new feature should integrate into this pipeline rather than bypassing it.

---

# Implemented Modules

The following modules are implemented and functional.

## Runtime

- Engine
- Lifecycle
- Service Container
- Dependency Injection
- Event Bus

---

## AI

- AIManager
- Ollama Provider
- Provider abstraction

---

## Identity

- IdentityProfile
- IdentityManager
- Dynamic system prompt
- Capability system

---

## Brain

- Brain
- Decision Engine
- Context Builder

---

## Conversation

- Conversation Manager
- Conversation History

---

## Memory

- SQLite storage
- Embeddings
- Vector similarity search
- Long-term memory
- Semantic recall
- Memory storage pipeline

---

## Context

- Context Manager
- Context Builder

---

## Perception

- Entity extraction foundation
- User message understanding

---

## Intent

- Intent detection
- Target extraction

---

## Planner

- Goal creation
- Plan generation

---

## Reasoning

- Plan validation
- Decision approval

---

## Execution

- Execution Manager
- Execution Executor

---

## Tools

Implemented:

- Tool base class
- Tool registry
- Launcher Tool
- Desktop application launcher
- Cached application discovery

---


---

## Monitor / Proactive

Implemented:

- Execution result monitoring
- Ambient awareness checks for calendar events, completed downloads, and hung windows
- Proactive speech for ambient signals

---

# Design Principles

The architecture follows strict separation of responsibilities.

Each module should perform one responsibility only.

Examples:

Conversation manages dialogue.

Memory stores information.

Recall retrieves information.

Planner creates plans.

Reasoning evaluates plans.

Execution performs plans.

Tools interact with the operating system.

No module should absorb responsibilities from another.

---

# Coding Principles

When adding new features:

Prefer creating new modules rather than expanding unrelated ones.

Avoid circular dependencies.

Inject dependencies through constructors whenever possible.

Keep classes focused on a single responsibility.

Avoid embedding business logic directly inside the Brain.

---

# Current Priorities

Development is currently focused on expanding desktop capabilities.

Highest priorities:

1. File Tool
2. Folder Tool
3. Browser Tool
4. URL Tool
5. Terminal Tool
6. VS Code Tool

After tool expansion:

- Window management
- Keyboard automation
- Mouse automation

---

# Long-Term Goals

Future milestones include:

- Reflection
- Autonomous planning
- Vision
- Voice
- Knowledge graph
- Multi-agent collaboration
- Plugin ecosystem
- Learning from experience

---

# Known Limitations

Current limitations include:

- Basic intent recognition
- Simple planning
- Minimal reasoning
- Limited tool set
- No autonomous execution
- No vision support
- No voice support
- No background tasks

These are expected and should not be treated as defects.

---

# Important Architectural Decisions

The following decisions should be preserved unless there is a compelling reason to change them.

- Identity owns EON's personality and system prompt.
- Brain orchestrates intelligence but does not own business logic.
- Memory stores information.
- Recall retrieves memories.
- Store decides what should be remembered.
- Planner generates plans.
- Reasoning approves plans.
- Execution performs plans.
- Tools interact with the operating system.

---

# Repository Conventions

Modules are located under:

```text
src/modules/
```

Project documentation is located under:

```text
docs/
```

Architecture documentation is located under:

```text
docs/architecture/
```

Module documentation is located under:

```text
docs/modules/
```

---

# Before Implementing a Feature

Always ask:

Does this belong inside an existing module?

or

Should this become a new module?

Favor modularity over convenience.

---

# Next Recommended Tasks

The recommended implementation order is:

1. Expand Tool framework
2. Improve Intent recognition
3. Improve Planner
4. Improve Reasoning
5. Implement Reflection
6. Build Vision module
7. Build Voice module
8. Autonomous task execution

---

# Notes for Future AI Assistants

This project values architecture over rapid feature development.

When extending EON:

- Preserve modularity.
- Avoid tightly coupling unrelated systems.
- Prefer composition over inheritance.
- Keep documentation synchronized with implementation.
- Update CHANGELOG.md, STATUS.md, CURRENT_TASK.md, and relevant module documentation whenever significant architectural changes are introduced.

The objective is to keep EON maintainable, extensible, and understandable by both humans and AI systems.
