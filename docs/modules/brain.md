# Brain Module

## Overview

The Brain Module is the central intelligence of EON.

It is responsible for transforming contextual information into intelligent responses by coordinating decision making, context construction, and communication with the language model.

The Brain itself does not store memories, execute tools, or perform planning directly. Instead, it orchestrates specialized modules that each handle a specific responsibility.

---

# Purpose

The Brain serves as EON's reasoning center.

Its responsibilities include:

- Understanding user requests
- Deciding how a request should be handled
- Constructing the complete LLM context
- Communicating with the AI provider
- Returning the final response

---

# Responsibilities

The Brain is responsible for:

- Decision making
- Context construction
- Identity-aware prompting
- Sending prompts to the language model
- Returning generated responses

The Brain is **not** responsible for:

- Memory storage
- Memory retrieval
- Tool execution
- Planning implementation
- Conversation storage

Those responsibilities belong to their respective modules.

---

# Architecture

```text
                User Message
                     │
                     ▼
             Conversation Manager
                     │
                     ▼
                  Brain
                     │
     ┌───────────────┼───────────────┐
     │               │               │
     ▼               ▼               ▼
Decision Engine  Context Builder   Identity
                     │
                     ▼
             Conversation History
                     │
                     ▼
                  Memories
                     │
                     ▼
                 AI Manager
                     │
                     ▼
              Language Model
                     │
                     ▼
             Assistant Response
```

---

# Components

## Brain

The Brain coordinates the complete thinking process.

Current responsibilities:

- Receive processed user input
- Decide how to respond
- Build context
- Call the AI Manager
- Return the final response

---

## DecisionEngine

The Decision Engine determines how EON should respond.

Examples include:

- Normal conversation
- Tool execution
- Future autonomous actions
- Future planning modes

Current implementation is intentionally lightweight and designed for future expansion.

---

## ContextBuilder

The Context Builder prepares the prompt sent to the language model.

It combines:

- Identity
- Conversation history
- Relevant long-term memories

The Brain never constructs prompts manually.

---

## AIManager

The AI Manager abstracts the language model provider.

Current provider:

- Ollama

Future providers may include:

- OpenAI
- Anthropic
- Google
- Local models

The Brain remains provider-independent.

---

# Thinking Pipeline

The Brain follows this pipeline for every request.

```text
User Message
      │
      ▼
Decision Engine
      │
      ▼
Context Builder
      │
      ▼
Identity Prompt
      │
      ▼
Conversation History
      │
      ▼
Relevant Memories
      │
      ▼
AI Manager
      │
      ▼
Language Model
      │
      ▼
Assistant Response
```

---

# Current Implementation

Implemented:

- Brain
- DecisionEngine
- ContextBuilder
- AIManager integration
- Identity-aware prompting
- Memory-aware prompting

---

# Future Improvements

Planned enhancements include:

- Multi-step reasoning
- Internal reflection
- Self-verification
- Tool planning
- Autonomous task execution
- Multi-agent collaboration
- Dynamic reasoning strategies
- Streaming responses

---

# Design Decisions

The Brain is intentionally lightweight.

Instead of implementing every capability itself, it delegates specialized work to dedicated modules.

Benefits include:

- Separation of concerns
- Easier testing
- Better scalability
- Modular architecture
- Provider independence

---

# Related Modules

- AI
- Conversation
- Context
- Identity
- Memory
- Planner
- Reasoning
- Tools

---

# Related Documentation

- identity.md
- context.md
- memory.md
- PROJECT.md
- architecture/overview.md
