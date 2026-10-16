# Perception Module

## Overview

The Perception Module is responsible for understanding raw user input before higher-level reasoning begins.

Its purpose is to transform natural language into structured information that other modules can consume.

Rather than simply passing text to the Brain, the Perception Module identifies important entities, topics, and contextual information from the user's message.

---

# Purpose

The Perception Module serves as EON's first stage of understanding.

It converts raw language into structured observations that improve reasoning, memory retrieval, and tool selection.

---

# Responsibilities

The Perception Module is responsible for:

- Reading user input
- Detecting entities
- Identifying important keywords
- Extracting conversation signals
- Preparing information for downstream modules

The Perception Module is **not** responsible for:

- Planning
- Reasoning
- Memory retrieval
- Tool execution
- Response generation

---

# Architecture

```text
          User Message
               │
               ▼
        Perception Module
               │
     ┌─────────┼─────────┐
     │         │         │
     ▼         ▼         ▼
  Entities   Topics   Signals
               │
               ▼
         Structured Result
               │
               ▼
             Brain
```

---

# Components

## PerceptionManager

The PerceptionManager coordinates the perception pipeline.

Current responsibilities include:

- Receiving user messages
- Producing structured perception results

Future versions will support multiple perception stages.

---

## PerceptionResult

The output produced by the perception system.

A perception result may contain:

- Entities
- Topics
- Keywords
- Intent hints
- Confidence scores

Other modules consume this structured information instead of parsing raw text repeatedly.

---

# Current Implementation

Currently implemented:

- PerceptionManager
- Basic PerceptionResult model
- Pipeline integration

Current extraction is intentionally lightweight and designed for future expansion.

---

# Future Improvements

Planned enhancements include:

- Named Entity Recognition (NER)
- Person detection
- Location detection
- Date and time extraction
- Task detection
- Relationship extraction
- Emotion detection
- Sentiment analysis
- Multi-language perception
- OCR perception
- Image perception
- Voice perception

---

# Example

User:

```text
Remind me to call John tomorrow at 3 PM.
```

Future perception result:

```text
Entities:
- Person: John
- Date: Tomorrow
- Time: 3 PM

Task:
- Reminder

Intent Hint:
- Reminder Creation
```

This structured representation allows downstream modules to work more accurately than parsing raw language repeatedly.

---

# Design Decisions

Perception is separated from reasoning.

The Brain should receive structured information rather than attempting to interpret every raw message from scratch.

Benefits include:

- Cleaner architecture
- Better scalability
- Easier testing
- Reduced duplicate parsing
- Improved reasoning quality

---

# Related Modules

- Brain
- Conversation
- Context
- Memory
- Recall
- Planner

---

# Related Documentation

- brain.md
- context.md
- memory.md
- PROJECT.md
- architecture/overview.md
