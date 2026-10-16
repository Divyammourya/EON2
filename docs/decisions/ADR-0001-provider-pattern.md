# ADR-0001: Provider Pattern

## Status

**Accepted**

---

# Context

EON integrates with multiple external services and libraries, including speech recognition engines, text-to-speech engines, language model providers, vector databases, and future plugin ecosystems.

Directly coupling application code to third-party SDKs would create several problems:

- Tight coupling
- Difficult testing
- Vendor lock-in
- Limited extensibility
- Increased maintenance cost
- Widespread code changes when replacing providers

The architecture required a mechanism to isolate external dependencies while allowing implementations to be replaced with minimal impact on the rest of the system.

---

# Decision

EON adopts the **Provider Pattern**.

Each external capability is represented by an abstract interface.

Concrete implementations encapsulate all interactions with third-party libraries.

Application code depends only on provider interfaces and never imports external SDKs directly.

Example:

```text
Application
      │
      ▼
VoiceProvider
      │
 ┌────┼─────────────────────────┐
 │    │                         │
 ▼    ▼                         ▼
OpenAIProvider   PiperProvider   FasterWhisperProvider
      │
      ▼
Third-Party SDK
```

Only provider implementations may import external libraries.

---

# Implementation Rules

Every provider must:

- Implement a common abstract interface.
- Translate third-party exceptions into project-defined exceptions.
- Encapsulate SDK-specific behavior.
- Manage its own lifecycle.
- Expose a consistent API regardless of implementation.

Providers should never expose SDK-specific objects to the rest of the application.

---

# Benefits

Adopting the Provider Pattern provides:

- Loose coupling
- Clear separation of concerns
- Easier testing through mocks and stubs
- Improved maintainability
- Easier provider replacement
- Better scalability
- Consistent interfaces
- Compliance with the Dependency Inversion Principle

---

# Alternatives Considered

## Direct SDK Usage

Every module would interact directly with external SDKs.

**Rejected because:**

- Strong coupling
- Difficult provider replacement
- SDK exceptions leak into application code
- Poor testability

---

## Service Locator

A central service locator would return provider implementations.

**Rejected because:**

- Hidden dependencies
- Reduced clarity
- Harder testing
- Encourages global state

---

## Dependency Injection Container

Use a full dependency injection framework.

**Rejected because:**

- Increased complexity
- Additional dependency
- Current project size does not justify a DI container

The current architecture achieves dependency inversion through explicit composition.

---

# Consequences

Positive:

- Providers are independently replaceable.
- Third-party dependencies remain isolated.
- Unit testing becomes straightforward.
- New providers can be added with minimal changes.

Negative:

- Additional abstraction layer.
- More interface definitions.
- Slight increase in boilerplate code.

These trade-offs are considered acceptable given the long-term maintainability benefits.

---

# Examples

Current provider implementations include:

## Voice

- FasterWhisperProvider
- PiperProvider
- OpenAIProvider

Future modules will follow the same pattern:

## LLM

- OpenAIProvider
- AnthropicProvider
- GeminiProvider
- OllamaProvider

## Memory

- OpenAIEmbeddingProvider
- SentenceTransformerProvider

## Storage

- SQLiteProvider
- PostgreSQLProvider
- ChromaProvider
- QdrantProvider

---

# Related Principles

This decision reinforces:

- Dependency Inversion Principle
- Open/Closed Principle
- Single Responsibility Principle
- Interface Segregation Principle

---

# References

- `docs/architecture/overview.md`
- `docs/architecture/components.md`
- `docs/architecture/voice.md`
- `docs/modules/voice.md`
- `docs/DESIGN_PRINCIPLES.md`
