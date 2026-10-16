# Store Module

## Overview

The Store Module is responsible for deciding what information should become part of EON's long-term memory.

Rather than saving every conversation, the Store Module evaluates incoming information and stores only memories considered valuable for future interactions.

This keeps EON's memory meaningful, efficient, and relevant.

---

# Purpose

The Store Module serves as EON's long-term memory writing system.

Its responsibilities include:

- Evaluating candidate memories
- Preventing duplicate memories
- Generating embeddings
- Persisting memories to storage

---

# Responsibilities

The Store Module is responsible for:

- Memory creation
- Duplicate detection
- Embedding generation
- Long-term memory storage
- Memory persistence

The Store Module is **not** responsible for:

- Memory retrieval
- Prompt construction
- Conversation history
- Planning
- Response generation

---

# Architecture

```text
          User Message
               │
               ▼
        Candidate Memory
               │
               ▼
        Store Manager
               │
       ┌───────┴────────┐
       ▼                ▼
Duplicate Check   Embedding Model
       │                │
       └───────┬────────┘
               ▼
        Memory Service
               │
               ▼
        SQLite Database
```

---

# Components

## StoreManager

The StoreManager coordinates the memory writing pipeline.

Responsibilities include:

- Receiving candidate memories
- Checking for duplicates
- Creating embeddings
- Saving memories

---

## MemoryService

The Store Module delegates persistence to the Memory Service.

The Memory Service is responsible for:

- Database communication
- Memory insertion
- Memory updates
- Memory retrieval

The Store Module never communicates with the database directly.

---

# Storage Pipeline

The memory writing process follows these steps:

1. Receive candidate memory.
2. Generate embedding.
3. Search for duplicates.
4. Determine similarity.
5. Store if unique.
6. Ignore if duplicate.

---

# Duplicate Detection

Before storing a memory, the Store Module performs semantic duplicate detection.

Example:

Existing memory:

```text
User's favorite programming language is Python.
```

Candidate memory:

```text
The user enjoys Python programming.
```

Although the wording differs, semantic similarity identifies these memories as representing the same information.

This prevents unnecessary duplication.

---

# Current Implementation

Implemented:

- StoreManager
- Embedding generation
- Duplicate detection
- SQLite persistence
- Memory Service integration

---

# Future Improvements

Planned enhancements include:

- Memory importance scoring
- Memory updating
- Memory expiration
- Memory reinforcement
- Episodic memory
- Confidence scoring
- Automatic memory summarization
- User-controlled memory editing

---

# Design Decisions

Writing memory is separated from reading memory.

The Store Module focuses exclusively on creating memories.

The Recall Module focuses exclusively on retrieving memories.

This separation allows each subsystem to evolve independently.

Benefits include:

- Cleaner architecture
- Independent optimization
- Better testing
- Easier maintenance
- Flexible storage strategies

---

# Related Modules

- Memory
- Recall
- Brain
- Context
- Identity

---

# Related Documentation

- memory.md
- recall.md
- context.md
- brain.md
- PROJECT.md
