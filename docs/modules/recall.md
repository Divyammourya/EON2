# Recall Module

## Overview

The Recall Module is responsible for retrieving relevant long-term memories from EON's memory system.

Rather than exposing the entire memory database to the language model, the Recall Module selects only the memories that are most relevant to the current conversation.

This keeps prompts compact while improving response quality.

---

# Purpose

The Recall Module acts as EON's semantic memory retrieval engine.

Its responsibilities include:

- Searching long-term memory
- Ranking memories by relevance
- Returning only useful memories
- Supplying contextual information to the Brain

---

# Responsibilities

The Recall Module is responsible for:

- Semantic memory search
- Similarity ranking
- Memory filtering
- Preparing memories for context injection

The Recall Module is **not** responsible for:

- Memory storage
- Embedding generation
- Prompt construction
- Response generation
- Planning

---

# Architecture

```text
            User Message
                 │
                 ▼
          Embedding Model
                 │
                 ▼
        Vector Similarity Search
                 │
                 ▼
        Ranked Memory Results
                 │
                 ▼
          Recall Manager
                 │
                 ▼
          Context Builder
                 │
                 ▼
               Brain
```

---

# Components

## RecallManager

The RecallManager coordinates semantic memory retrieval.

Responsibilities include:

- Receiving user queries
- Searching memory
- Ranking results
- Returning relevant memories

---

# Retrieval Pipeline

The retrieval process follows these steps:

1. Receive the user's message.
2. Generate an embedding.
3. Compare it against stored embeddings.
4. Calculate similarity scores.
5. Rank matching memories.
6. Return the most relevant memories.

Only the highest-ranking memories are injected into the language model.

---

# Similarity Search

The Recall Module currently performs semantic similarity search.

This allows EON to remember information based on meaning rather than exact wording.

For example:

Stored memory:

```text
Divyam enjoys programming in Python.
```

User asks:

```text
What programming language do I like?
```

Even though the wording differs, semantic similarity retrieves the correct memory.

---

# Current Implementation

Implemented:

- RecallManager
- Embedding-based retrieval
- Similarity ranking
- Top-memory selection
- Context integration

---

# Future Improvements

Planned enhancements include:

- Memory decay
- Importance weighting
- Time-aware ranking
- User preference prioritization
- Episodic memory retrieval
- Multi-document recall
- Memory clustering
- Hybrid keyword + vector search

---

# Design Decisions

Recall is intentionally separated from storage.

Memory storage focuses on persistence.

Recall focuses on retrieval.

This separation allows retrieval strategies to evolve without changing the storage layer.

Benefits include:

- Cleaner architecture
- Independent optimization
- Better scalability
- Easier experimentation
- Multiple retrieval algorithms

---

# Related Modules

- Memory
- Store
- Context
- Brain
- Identity

---

# Related Documentation

- memory.md
- context.md
- brain.md
- PROJECT.md
- architecture/overview.md
