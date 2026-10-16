# Memory Module

## Purpose

The Memory module is responsible for storing, organizing, retrieving, and managing conversational knowledge within EON.

It provides both short-term and long-term memory while remaining independent of any specific embedding model, vector database, or storage engine.

The module allows the assistant to retain relevant information across interactions and provide contextual responses.

---

# Responsibilities

The Memory module is responsible for:

- Conversation history
- Working memory
- Long-term memory
- Semantic search
- Embedding management
- Context retrieval
- Memory summarization
- Memory persistence
- Memory ranking
- Context assembly

The module is **not** responsible for:

- Language generation
- Speech processing
- User interface
- Plugin execution

---

# High-Level Architecture

```text
Application
      │
      ▼
MemoryManager
      │
      ▼
MemoryStore
      │
 ┌────┼──────────────────────────────┐
 │    │                              │
 ▼    ▼                              ▼
EmbeddingProvider            StorageProvider
      │                              │
      ▼                              ▼
Embedding Model            Database / Vector Store
```

The application communicates only with the `MemoryManager`.

---

# Core Components

## MemoryManager

Coordinates all memory operations.

Responsibilities include:

- Store memories
- Retrieve memories
- Delete memories
- Update memories
- Summarize conversations
- Build LLM context
- Manage providers

---

## MemoryStore

Acts as the central storage interface.

Responsibilities:

- Persist memories
- Query memories
- Remove memories
- Update memories

The rest of the module depends only on this abstraction.

---

## EmbeddingProvider

Responsible for converting text into vector embeddings.

Possible providers include:

- OpenAI
- Ollama
- Sentence Transformers
- Hugging Face
- Local embedding models

---

## StorageProvider

Responsible for persistent storage.

Possible implementations include:

- SQLite
- PostgreSQL
- ChromaDB
- FAISS
- Qdrant
- Pinecone

---

# Planned Directory Structure

```text
memory/

├── manager.py
├── models.py
├── exceptions.py
├── providers/
│   ├── embeddings/
│   └── storage/
├── retrieval/
├── summarization/
├── utils/
└── __init__.py
```

---

# Memory Types

## Working Memory

Temporary memory used during the current conversation.

Characteristics:

- Fast
- Volatile
- Automatically discarded

---

## Long-Term Memory

Persistent information retained across conversations.

Characteristics:

- Persistent
- Searchable
- User-specific
- Editable

---

## Semantic Memory

Stores vector representations of information.

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
      │
      ▼
LLM Context
```

Only the most relevant memories should be returned.

---

# Storage Flow

```text
Conversation
      │
      ▼
Extract Information
      │
      ▼
Generate Embedding
      │
      ▼
Store Memory
```

The storage implementation remains hidden behind provider interfaces.

---

# Context Assembly

Before an LLM request is made, the Memory module assembles contextual information.

Context may include:

- Recent conversation
- Retrieved memories
- User preferences
- Conversation summaries
- Relevant facts

The resulting context is passed to the LLM module.

---

# Thread Safety

The Memory module is responsible for protecting shared mutable state.

Potential synchronization includes:

- Cache locks
- Storage locks
- Index update locks
- Background summarization tasks

---

# Error Handling

The module exposes only Memory-specific exceptions.

Third-party storage, embedding, and database exceptions are translated into project-defined exception types.

No external exceptions should escape the module.

---

# Future Features

Planned capabilities include:

- Automatic conversation summarization
- Memory importance scoring
- Memory decay
- Memory editing
- User profiles
- Multi-user support
- Hybrid search
- Knowledge graph integration
- Background indexing
- Memory compression

---

# Design Principles

The module follows:

- Single Responsibility Principle
- Dependency Inversion Principle
- Open/Closed Principle
- Provider Pattern
- Repository Pattern
- Composition over inheritance

---

# Current Status

Current implementation:

- Planning

Planned next steps:

- Define memory models
- Create provider interfaces
- Implement storage abstraction
- Implement embedding providers
- Add retrieval engine
- Add summarization pipeline
- Integrate with the LLM module

---

# Related Documents

- ../architecture/memory.md
- ../architecture/storage.md
- ../decisions/ADR-0004-memory-architecture.md
