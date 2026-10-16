# EON Architecture Overview

EON is a modular, local-first AI operating system designed around independent components.

Rather than placing all intelligence inside a single assistant class, responsibilities are separated into specialized modules.

Each module performs one job and communicates with other modules through well-defined interfaces.

---

# High-Level Architecture

```text
                    User
                      │
                      ▼
               Conversation
                      │
                      ▼
                Perception
                      │
                      ▼
                  Recall
                      │
                      ▼
                  Context
                      │
                      ▼
                   Brain
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       Intent      Planner    Reasoning
          │           │           │
          └───────────┼───────────┘
                      ▼
                 Execution
                      │
                      ▼
                    Tools
                      │
                      ▼
              Operating System
```

---

# Module Responsibilities

## Conversation

Handles interaction between the user and EON.

Responsibilities:

- Conversation history
- User messages
- Assistant responses

---

## Perception

Processes raw user input.

Responsibilities:

- Entity extraction
- Initial understanding
- Context preparation

---

## Recall

Searches long-term memory.

Responsibilities:

- Semantic search
- Memory retrieval
- Similarity ranking

---

## Context

Builds the complete context supplied to the Brain.

Responsibilities:

- Conversation history
- Identity
- Relevant memories

---

## Brain

Coordinates intelligence.

Responsibilities:

- Decision orchestration
- AI interaction
- Context usage

The Brain should never directly contain unrelated business logic.

---

## Intent

Determines what the user wants.

Examples:

- Chat
- Launch application
- Search memory
- Open file

---

## Planner

Creates plans for accomplishing user requests.

Plans consist of:

- Goals
- Steps
- Actions

---

## Reasoning

Evaluates plans before execution.

Responsibilities:

- Validation
- Approval
- Safety checks

---

## Execution

Executes approved plans.

Coordinates tools and operating-system interactions.

---

## Tools

Interact with the outside world.

Examples:

- Launcher Tool
- File Tool
- Browser Tool
- Terminal Tool

Each tool performs one responsibility.

---

## Monitor

Observes execution results and ambient computer state.

Responsibilities:

- Execution result summaries
- Ambient signal detection
- Meeting, download, and hung-window awareness

---

## Proactive

Speaks or surfaces useful information without waiting for a direct request.

Responsibilities:

- Scheduled reminders
- Idle check-ins
- Ambient signal delivery

---

## Memory

Stores long-term information.

Responsibilities:

- Embeddings
- SQLite storage
- Similarity search
- Duplicate detection

---

## Identity

Defines who EON is.

Responsibilities:

- System prompt
- Creator
- Capabilities
- Personality
- Version information

Identity owns all information about EON itself.

---

# Design Principles

The architecture follows several principles.

## Single Responsibility

Every module performs one responsibility.

---

## Dependency Injection

Modules receive dependencies through constructors.

Avoid global state whenever possible.

---

## Loose Coupling

Modules communicate through interfaces rather than direct implementation details.

---

## Extensibility

New capabilities should usually become new modules instead of modifying unrelated code.

---

# Current Module Layout

```text
src/modules/

ai/
brain/
conversation/
context/
execution/
identity/
intent/
memory/
perception/
planner/
reasoning/
recall/
reflection/
store/
tools/
```

Each directory represents an independent subsystem.

---

# Future Architecture

Future modules are expected to include:

- Vision
- Voice
- Automation
- Reflection
- Knowledge Graph
- Scheduler
- Agent Framework

The existing architecture is designed so these modules can be added without restructuring the current system.

---

# Development Philosophy

Architecture takes priority over feature count.

Every feature should:

- fit naturally into an existing module, or
- justify the creation of a new module.

Maintaining modularity is considered more important than minimizing file count.
