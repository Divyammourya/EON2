# ADR-0004: Memory Architecture

## Status

**Accepted**

---

# Context

One of EON's primary goals is to function as a persistent AI assistant capable of remembering relevant information across conversations.

Without a dedicated memory subsystem, every interaction would be isolated, preventing long-term personalization, semantic retrieval, and contextual reasoning.

A separate architecture was needed to manage memory independently from the LLM while remaining flexible enough to support different embedding models and storage technologies.

---

# Decision

EON adopts a modular memory architecture composed of independent layers.

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

Each layer has a single responsibility and communicates only through well-defined interfaces.

---

# Architectural Principles

The Memory subsystem follows these principles:

- Separation of concerns
- Provider abstraction
- Dependency inversion
- Composition over inheritance
- Extensibility
- Storage independence

The application communicates only with the `MemoryManager`.

---

# Memory Types

The architecture supports multiple categories of memory.

## Working Memory

Temporary information retained only for the current interaction.

Examples:

- Active conversation
- Intermediate reasoning
- Temporary variables

---

## Long-Term Memory

Persistent information stored across conversations.

Examples:

- User preferences
- Important facts
- Learned information
- Historical conversations

---

## Semantic Memory

Vector representations used for similarity search.

These memories enable retrieval of context based on meaning rather than exact wording.

---

# Embedding Providers

Embedding generation is abstracted behind an `EmbeddingProvider` interface.

Potential implementations include:

- OpenAI Embeddings
- Sentence Transformers
- Hugging Face models
- Ollama embeddings
- Local embedding models

Changing embedding providers should require no changes to application logic.

---

# Storage Providers

Persistent storage is abstracted behind a `StorageProvider` interface.

Planned implementations include:

- SQLite
- PostgreSQL
- ChromaDB
- FAISS
- Qdrant
- Pinecone

This allows storage technology to evolve independently of the Memory module.

---

# Retrieval Pipeline

Memory retrieval follows a consistent workflow.

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

Only the most relevant memories are included in the final context sent to the LLM.

---

# Why Memory Is Separate from the LLM

The Memory subsystem is intentionally independent from the LLM module.

Reasons include:

- Different responsibilities
- Easier testing
- Provider independence
- Reusable memory APIs
- Support for multiple LLM providers

The LLM consumes context but does not manage memory directly.

---

# Alternatives Considered

## Storing Everything in Conversation History

Every previous conversation would be sent to the LLM.

**Rejected because:**

- Token limits
- High cost
- Poor scalability
- Slow responses

---

## Embedding Logic Inside the LLM Module

Embedding generation would be part of the LLM subsystem.

**Rejected because:**

- Violates separation of concerns
- Couples memory to a specific LLM provider
- Reduces flexibility

---

## Fixed Database Implementation

Choose a single storage backend permanently.

**Rejected because:**

- Vendor lock-in
- Difficult migration
- Limited flexibility

---

# Consequences

Positive:

- Modular design
- Independent provider replacement
- Scalable architecture
- Better maintainability
- Easier testing
- Future-proof storage options

Negative:

- Additional abstraction layers
- More interfaces to maintain
- Increased implementation complexity

These trade-offs are considered worthwhile for long-term scalability.

---

# Future Enhancements

The architecture supports future capabilities such as:

- Hybrid retrieval
- Memory importance scoring
- Automatic summarization
- Memory decay
- Knowledge graphs
- Background indexing
- Multi-user memory
- Distributed storage
- Cross-device synchronization

These features can be introduced without changing the public Memory API.

---

# Related Principles

This decision reinforces:

- Single Responsibility Principle
- Dependency Inversion Principle
- Open/Closed Principle
- Repository Pattern
- Provider Pattern

---

# References

- `docs/architecture/memory.md`
- `docs/architecture/storage.md`
- `docs/modules/memory.md`
- `docs/decisions/ADR-0001-provider-pattern.md`
- `docs/DESIGN_PRINCIPLES.md`
