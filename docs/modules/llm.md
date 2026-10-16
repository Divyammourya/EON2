# LLM Module

## Purpose

The LLM module is responsible for all interactions with large language models (LLMs) inside EON.

It provides a provider-independent interface for text generation, reasoning, structured outputs, embeddings, tool calling, streaming, and future multimodal capabilities.

The rest of the system never communicates with OpenAI or any other LLM SDK directly. Every interaction flows through the abstractions defined by this module.

---

# Responsibilities

The LLM module is responsible for:

- Managing LLM providers
- Creating chat completions
- Streaming responses
- Structured JSON generation
- Function/tool calling
- Embedding generation
- Conversation context handling
- Token accounting
- Model selection
- Provider failover (future)
- Retry policies
- Response validation

The module is **not** responsible for:

- Long-term memory
- Speech recognition
- Speech synthesis
- Plugin execution
- Business logic

---

# High-Level Architecture

```
Application
      │
      ▼
LLMManager
      │
      ▼
LLMProvider (abstract)
      │
 ┌────┴────────────┐
 │                 │
 ▼                 ▼
OpenAIProvider   Future Providers
                 (Anthropic, Gemini,
                 Ollama, LM Studio,
                 Azure OpenAI...)
```

The application depends only on the abstractions.

Concrete providers remain isolated.

---

# Core Components

## LLMManager

Acts as the orchestration layer.

Responsibilities:

- Select provider
- Manage conversations
- Route requests
- Retry failures
- Handle provider lifecycle
- Future provider fallback

---

## LLMProvider

Abstract interface implemented by every provider.

Example responsibilities:

- generate()
- stream()
- embed()
- count_tokens()
- health_check()
- initialize()
- shutdown()

---

## OpenAIProvider

Concrete implementation using the OpenAI SDK.

Responsibilities:

- Chat Completions
- Responses API
- Streaming
- Tool Calling
- Structured Output
- Embeddings
- Authentication

Only this provider imports:

```
openai
```

No other module imports the SDK.

---

# Planned Directory Structure

```
llm/

├── manager.py
├── exceptions.py
├── models.py
├── providers/
│   ├── base.py
│   ├── openai_provider.py
│   ├── anthropic_provider.py
│   ├── ollama_provider.py
│   └── gemini_provider.py
│
├── prompts/
│
├── tools/
│
└── utils/
```

---

# Provider Pattern

Every LLM provider implements the same interface.

Example:

```
LLMProvider

    generate()

    stream()

    embed()

    initialize()

    shutdown()

    health_check()
```

This allows providers to be swapped without modifying application code.

---

# Conversation Flow

```
User Input
      │
      ▼
Conversation Manager
      │
      ▼
Prompt Builder
      │
      ▼
LLM Provider
      │
      ▼
LLM Response
      │
      ▼
Application
```

---

# Prompt Construction

Prompt construction will eventually combine:

- System Prompt
- Developer Prompt
- User Prompt
- Memory Context
- Retrieved Knowledge
- Tool Results
- Conversation History

before sending the final request to the selected provider.

---

# Streaming

The module will support incremental token streaming.

Example flow:

```
Provider

↓

Token

↓

Token

↓

Token

↓

Final Response
```

Streaming allows:

- faster UI updates
- lower perceived latency
- interruption support
- voice synthesis while generating

---

# Structured Output

The module will support structured responses using schemas.

Example:

```
Input

↓

LLM

↓

Validated JSON

↓

Application
```

This minimizes parsing errors and improves reliability.

---

# Tool Calling

Future providers may expose native tool/function calling.

Example:

```
User

↓

LLM

↓

Tool Request

↓

Plugin Manager

↓

Tool Result

↓

LLM

↓

Final Response
```

The LLM module coordinates provider interactions but does not execute tools itself.

---

# Embeddings

The module will provide embedding generation for:

- Memory retrieval
- Semantic search
- Vector databases
- Document indexing
- Knowledge retrieval

---

# Context Management

The module will eventually manage:

- conversation history
- token limits
- automatic truncation
- context windows
- summarization

This keeps prompts within model constraints.

---

# Error Handling

The module translates provider-specific exceptions into project-specific exceptions.

Example:

```
OpenAI Error

↓

LLMProviderError

↓

Application
```

No third-party exceptions should escape the module.

---

# Future Providers

Planned providers include:

- OpenAI
- Anthropic
- Google Gemini
- Ollama
- LM Studio
- Azure OpenAI
- Local Transformers

Adding a new provider should require only implementing the provider interface.

---

# Design Principles

The module follows:

- SOLID
- Dependency Inversion
- Interface Segregation
- Composition over inheritance
- Provider abstraction
- Clean Architecture
- Explicit error translation

---

# Current Status

Current implementation:

- Planning

Planned next steps:

- Define provider interfaces
- Design models
- Create manager
- Implement OpenAI provider
- Add streaming
- Add structured outputs
- Add embeddings
- Add tool calling
- Add provider fallback
```
