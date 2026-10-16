# Context Module

## Overview

The Context Module is responsible for building the complete conversational context used by EON before every interaction with the language model.

Rather than allowing the Brain to construct prompts manually, this module gathers information from multiple subsystems—including Identity, Conversation History, and Memory—and produces a unified context.

This separation keeps prompt construction independent from reasoning, making the system easier to maintain and extend.

---

# Purpose

The Context Module ensures that EON never responds using only the user's latest message.

Instead, responses are generated using contextual information collected from across the system.

The module acts as the bridge between:

- Identity
- Conversation History
- Long-Term Memory
- Brain

---

# Responsibilities

The Context Module is responsible for:

- Building conversational context
- Injecting EON's identity prompt
- Including relevant long-term memories
- Including recent conversation history
- Preparing messages for the LLM

The Context Module is **not** responsible for:

- Memory storage
- Memory retrieval
- Planning
- Reasoning
- Tool execution

---

# Architecture

```text
                 Identity
                     │
                     │
Conversation ────────┼────── Memory
                     │
                     ▼
             Context Builder
                     │
                     ▼
                  Brain
                     │
                     ▼
                    LLM
```

---

# Components

## ContextBuilder

The ContextBuilder assembles the final prompt delivered to the language model.

Current responsibilities include:

- Loading EON's identity prompt
- Injecting relevant long-term memories
- Appending conversation history
- Producing the final message list

---

## ContextManager

The ContextManager coordinates context-related operations throughout the application.

Current responsibilities include:

- Managing conversational context
- Coordinating context construction

Future responsibilities may include:

- Topic tracking
- Conversation summarization
- Active task tracking
- User preference context
- Session state

---

# Context Sources

## Identity

Provides:

- Assistant name
- Creator
- Version
- Description
- Capabilities
- Personality
- System prompt

---

## Conversation

Provides:

- Recent user messages
- Recent assistant messages

---

## Memory

Provides:

- Relevant long-term memories
- Semantic recall results

Only relevant memories are injected into the final prompt.

---

# Data Flow

```text
User Message
      │
      ▼
Conversation History
      │
      ▼
Relevant Memories
      │
      ▼
Identity Prompt
      │
      ▼
ContextBuilder
      │
      ▼
Brain
      │
      ▼
Language Model
```

---

# Current Implementation

Implemented:

- ContextBuilder
- ContextManager
- Identity-aware prompts
- Conversation history integration
- Memory injection

---

# Future Improvements

Planned enhancements include:

- Conversation summarization
- Topic tracking
- Active goals
- Session state
- User preference context
- Multi-document context
- Token budgeting
- Intelligent context compression

---

# Design Decisions

The Context Module exists to separate prompt construction from reasoning.

The Brain should focus on decision-making, while the Context Module focuses exclusively on preparing the information supplied to the language model.

This improves:

- Separation of concerns
- Maintainability
- Testability
- Reusability
- Scalability

---

# Related Modules

- Brain
- Conversation
- Identity
- Memory
- Recall

---

# Related Documentation

- `identity.md`
- `memory.md`
- `PROJECT.md`
- `architecture/overview.md`
