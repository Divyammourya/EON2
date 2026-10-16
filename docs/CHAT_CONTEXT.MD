# Chat Context

## Purpose

This document explains how conversational context is managed throughout EON.

It describes the lifecycle of conversation state, the interaction between modules, and the strategy used to construct context for Large Language Models (LLMs).

This is an architectural reference and does not define provider-specific implementations.

---

# Goals

The chat context system should:

- Maintain coherent multi-turn conversations.
- Minimize unnecessary token usage.
- Integrate relevant memories.
- Support tool and plugin outputs.
- Remain provider-independent.
- Scale to long-running conversations.

---

# High-Level Flow

```text
User Message
      │
      ▼
Conversation Manager
      │
      ▼
Context Builder
      │
      ├──────────────┐
      ▼              ▼
Short-Term      Long-Term
Memory          Memory
      │              │
      └──────┬───────┘
             ▼
      Prompt Assembly
             │
             ▼
        LLM Provider
             │
             ▼
       Assistant Response
             │
             ▼
Conversation History
```

---

# Context Components

A complete context may contain:

- System prompt
- Conversation history
- Retrieved memories
- Active user profile
- Plugin outputs
- Tool results
- Runtime metadata
- Current user message

Not every component is required for every request.

---

# Context Layers

## 1. System Prompt

Defines the assistant's identity, behavior, constraints, and capabilities.

Examples include:

- Personality
- Safety rules
- Global instructions
- Available tools

---

## 2. Conversation History

Contains recent exchanges between the user and the assistant.

Purpose:

- Preserve conversational continuity.
- Resolve references.
- Maintain dialogue flow.

The amount of retained history may vary depending on model limits.

---

## 3. Short-Term Memory

Stores information relevant only to the current session.

Examples:

- Current task
- Temporary preferences
- Recent tool outputs

Short-term memory is discarded when the session ends unless promoted.

---

## 4. Long-Term Memory

Stores persistent information across conversations.

Examples:

- User preferences
- Important facts
- Learned habits
- Persistent settings

Relevant memories are retrieved semantically and injected into the prompt.

---

## 5. Tool Results

Results produced by plugins or internal tools.

Examples:

- Search results
- File contents
- Calculations
- API responses

Only relevant outputs should be included.

---

## 6. Current User Message

The latest user input is always appended as the final message before sending the request to the LLM.

---

# Context Builder

The Context Builder is responsible for:

- Collecting conversation history.
- Retrieving relevant memories.
- Filtering unnecessary information.
- Respecting token limits.
- Assembling the final prompt.

It acts as the bridge between memory, plugins, and the LLM.

---

# Token Management

Context should remain within the selected model's token limit.

Strategies include:

- Truncating old messages.
- Summarizing conversations.
- Limiting retrieved memories.
- Excluding irrelevant tool outputs.

The most relevant information should always be prioritized.

---

# Memory Retrieval

Long-term memories should be retrieved using semantic similarity rather than simple keyword matching.

Potential ranking factors:

- Similarity score
- Recency
- Importance
- Frequency
- User-defined priority

---

# Context Lifecycle

```text
User Input
      │
      ▼
Store Message
      │
      ▼
Retrieve Memories
      │
      ▼
Build Context
      │
      ▼
Generate Response
      │
      ▼
Store Assistant Response
      │
      ▼
Update Memory (optional)
```

---

# Provider Independence

The chat context system must remain independent of any specific LLM provider.

It should produce a generic conversation representation that can be translated into the request format required by individual providers.

This allows switching providers without changing context management logic.

---

# Future Enhancements

Potential improvements include:

- Automatic conversation summarization.
- Dynamic context compression.
- Memory importance scoring.
- Context caching.
- Multi-agent shared context.
- Context visualization tools.

---

# Design Principles

The context system should remain:

- Modular
- Extensible
- Provider-independent
- Memory-aware
- Token-efficient
- Deterministic where practical

---

# Related Documentation

- `architecture/llm.md`
- `architecture/memory.md`
- `modules/llm.md`
- `modules/memory.md`
- `FUTURE_ARCHITECTURE.md`
