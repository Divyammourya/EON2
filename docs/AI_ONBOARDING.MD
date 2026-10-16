# AI Onboarding Guide

This document is intended for AI assistants (GPT, Claude, Gemini, DeepSeek, etc.) that continue the development of EON.

Read this document completely before modifying the codebase.

---

# Project Goal

EON is not intended to be "another chatbot."

The objective is to build a modular, local-first AI operating system capable of understanding users, reasoning about tasks, planning actions, interacting with the operating system, remembering information, and continuously evolving.

Every architectural decision should support long-term extensibility rather than short-term convenience.

---

# Core Philosophy

When extending EON, prioritize:

1. Architecture
2. Modularity
3. Readability
4. Extensibility
5. Performance

Avoid shortcuts that increase coupling between modules.

---

# Architecture Overview

EON follows a modular architecture.

Current request flow:

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

Operating System

↓

Response
```

Each module owns exactly one responsibility.

---

# Module Responsibilities

Conversation

- Handles user interaction.
- Stores recent messages.

Perception

- Understands user input.
- Extracts entities.

Recall

- Retrieves semantic memories.

Context

- Builds prompt context.

Identity

- Defines who EON is.

Brain

- Coordinates intelligence.

Intent

- Determines user intention.

Planner

- Creates plans.

Reasoning

- Evaluates plans.

Execution

- Executes approved plans.

Tools

- Interact with the operating system.

Memory

- Stores long-term knowledge.

---

# What Should Never Change

The following architectural principles should remain stable unless there is a compelling reason to redesign the system.

## Identity owns identity.

Do not hardcode system prompts inside Brain.

---

## Brain coordinates.

Brain should orchestrate modules.

Brain should not become a "God Object."

---

## Memory stores.

Memory should never decide whether something is relevant.

That belongs to Recall.

---

## Recall retrieves.

Recall should not permanently store information.

---

## Store stores.

Store decides what should become long-term memory.

---

## Planner plans.

Planner should not execute actions.

---

## Execution executes.

Execution should never create plans.

---

## Tools interact with the operating system.

Tools should never contain conversation logic.

---

# Dependency Rules

Prefer constructor dependency injection.

Avoid global variables.

Avoid hidden singletons.

Avoid circular imports.

---

# Coding Style

Prefer:

Small classes.

Small methods.

Explicit names.

Composition over inheritance.

Type hints.

Dataclasses where appropriate.

Meaningful comments only when necessary.

---

# Documentation Rules

Whenever a new module is added:

Update:

- CHANGELOG.md
- STATUS.md
- PROJECT.md
- SESSION_HANDOFF.md
- architecture/overview.md
- modules/<module>.md

Documentation is considered part of the implementation.

---

# Current Priorities

Highest priority work:

1. Tool framework
2. File Tool
3. Folder Tool
4. Browser Tool
5. Terminal Tool
6. VS Code Tool
7. Window Manager
8. Mouse Automation
9. Keyboard Automation

---

# Future Roadmap

Planned major systems:

- Reflection
- Vision
- Voice
- Scheduler
- Autonomous Tasks
- Knowledge Graph
- Plugin Ecosystem
- Multi-Agent Collaboration

---

# Repository Layout

```text
docs/
src/

src/modules/
src/core/
src/bootstrap/
```

Each directory has a dedicated responsibility.

---

# Before Adding Code

Ask these questions:

Does this belong in an existing module?

If not,

Should it become a new module?

If neither answer is clear, redesign before implementing.

---

# When Unsure

Prefer improving architecture instead of adding features quickly.

Maintain consistency with existing design patterns.

Preserve modularity.

Avoid breaking public interfaces unless absolutely necessary.

---

# Mission

The goal is to transform EON into a maintainable, extensible AI operating system that can continue evolving for years.

Every contribution should make the architecture clearer rather than more complicated.
