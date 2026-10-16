# Memory Architecture

## Purpose

This document describes the planned architecture of the EON Memory module.

The Memory module will be responsible for storing, retrieving, organizing, and summarizing conversational knowledge while remaining independent of any specific storage engine, embedding model, or vector database.

---

# Status

**Planned**

The architecture described here represents the intended design and may evolve as implementation progresses.

---

# Goals

The Memory module is designed to provide:

- Persistent memory
- Short-term conversational memory
- Long-term knowledge storage
- Efficient semantic retrieval
- Provider independence
- Scalable storage
- Extensibility
- Testability

---

# Responsibilities

The Memory module will be responsible for:

- Conversation history
- Semantic memory
- Memory retrieval
- Memory summarization
- Memory persistence
- Embedding generation
- Memory indexing
- Context assembly

The Memory module will not be responsible for:

- Language model inference
- Speech processing
- User interface
- Plugin execution

---

# High-Level Architecture

```text
                Application
                     │
                     ▼
              Memory Manager
                     │
         ┌───────────┴───────────┐
         │                       │
   Memory Retrieval      Memory Storage
         │                       │
         ▼                       ▼
 Embedding Provider     Storage Provider
```

---

# Planned Components

The Memory module will consist of:

- Memory Manager
- Memory Store
- Retrieval Engine
- Embedding Provider
- Storage Provider
- Memory Models
- Memory Exceptions

Each component has a single, clearly defined responsibility.

---

# Memory Types

## Working Memory

Stores information relevant only to the current conversation.

Characteristics:

- Temporary
- Fast access
- Automatically discarded

---

## Long-Term Memory

Stores persistent information across conversations.

Characteristics:

- Persistent
- Searchable
- Summarizable
- User-specific

---

## Semantic Memory

Stores information represented as vector embeddings.

Used for:

- Similarity search
- Context retrieval
- Knowledge lookup

---

# Retrieval Pipeline

```text
User Query
     │
     ▼
Embedding Generation
     │
     ▼
Vector Search
     │
     ▼
Ranking
     │
     ▼
Retrieved Memories
```

Only relevant memories should be returned.

---

# Storage Architecture

Memory storage will be abstracted behind interfaces.

Possible implementations include:

- SQLite
- PostgreSQL
- ChromaDB
- FAISS
- Qdrant
- Pinecone

Application code should remain unaware of the underlying storage implementation.

---

# Embedding Providers

Embeddings will also be abstracted.

Potential providers include:

- OpenAI
- Ollama
- Sentence Transformers
- Hugging Face
- Local embedding models

---

# Memory Lifecycle

```text
Conversation

↓

Capture Information

↓

Generate Embeddings

↓

Store Memory

↓

Retrieve Later

↓

Summarize

↓

Archive
```

---

# Context Assembly

Retrieved memories will be assembled into contextual information before being passed to the LLM.

The Memory module determines:

- Which memories are relevant
- Retrieval order
- Memory limits
- Context formatting

---

# Thread Safety

The Memory module will protect shared mutable state internally.

Potential synchronization includes:

- Cache locks
- Storage locks
- Index update locks

---

# Error Handling

The module will expose only Memory-specific exceptions.

Third-party storage and embedding exceptions will be translated into EON exception types.

---

# Future Features

Planned capabilities include:

- Automatic summarization
- Memory importance scoring
- Memory decay
- Memory editing
- User profiles
- Multi-user support
- Memory versioning
- Hybrid retrieval
- Knowledge graphs

---

# Design Principles

The Memory module will follow:

- Single Responsibility Principle
- Dependency Inversion Principle
- Open/Closed Principle
- Composition over Inheritance

---

# Related Documents

- overview.md
- components.md
- storage.md
- ../modules/memory.md
- ../decisions/ADR-0004-memory-architecture.md
