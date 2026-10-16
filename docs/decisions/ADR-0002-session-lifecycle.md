# ADR-0002: Explicit Session Lifecycle

## Status

**Accepted**

---

# Context

Several EON modules manage resources that exist only for the duration of an interaction.

Examples include:

- Voice recognition sessions
- Speech synthesis requests
- Streaming LLM conversations
- Future plugin executions
- Background workflows

Allowing providers to create and destroy state implicitly would make resource ownership unclear and increase the risk of leaks, invalid state, and inconsistent behavior.

A consistent lifecycle was required for all stateful components.

---

# Decision

EON adopts an explicit session lifecycle managed by the application.

Every stateful provider follows the same lifecycle:

```text
Create Session

↓

Start Session

↓

Perform Operations

↓

Stop Session

↓

Destroy Session
```

Providers never create sessions themselves.

Instead, sessions are created by the application and passed to providers.

Providers validate that a session is active before performing any operation.

---

# Session Ownership

Session objects belong to the application.

Providers may:

- Read session data
- Update session metadata
- Validate session state

Providers may not:

- Create sessions
- Replace session objects
- Destroy sessions
- Share sessions between unrelated operations

This keeps ownership centralized and predictable.

---

# Session Registration

Providers maintain an internal registry of active sessions.

Typical operations include:

- Register session
- Validate session
- Remove session

Attempting to use an inactive session results in a `VoiceSessionError` (or an equivalent module-specific exception).

---

# Benefits

Using an explicit lifecycle provides:

- Clear ownership
- Predictable resource management
- Easier debugging
- Better thread safety
- Consistent behavior across providers
- Simpler testing
- Reduced risk of resource leaks

---

# Alternatives Considered

## Implicit Session Creation

Providers would automatically create sessions when operations begin.

**Rejected because:**

- Hidden state
- Unclear ownership
- Harder debugging
- Difficult lifecycle management

---

## Global Singleton Session

A single global session shared across the application.

**Rejected because:**

- Poor scalability
- No support for concurrent operations
- High coupling
- Difficult testing

---

## Stateless Providers

Providers would maintain no session state.

**Rejected because:**

Some providers require runtime metadata, active resources, or operation-specific state that naturally belongs to a session.

---

# Consequences

Positive:

- Consistent lifecycle across modules
- Easier reasoning about state
- Supports concurrent sessions
- Improves reliability

Negative:

- Slightly more boilerplate
- Additional validation logic
- Session management responsibilities for the application

These trade-offs are acceptable for improved maintainability and correctness.

---

# Current Implementation

The Voice module already follows this lifecycle.

Example provider methods include:

- `start_session()`
- `stop_session()`
- `transcribe()`
- `transcribe_stream()`
- `speak()`
- `stop_speaking()`

Each operation validates that the session is currently active.

---

# Future Usage

This lifecycle will also be adopted by:

- LLM conversations
- Memory operations
- Plugin execution contexts
- Workflow execution
- Agent sessions

Maintaining a common lifecycle across modules simplifies orchestration and improves consistency.

---

# Related Principles

This decision reinforces:

- Single Responsibility Principle
- Explicit Resource Ownership
- Composition over Inheritance
- Fail Fast
- Defensive Programming

---

# References

- `docs/architecture/voice.md`
- `docs/architecture/components.md`
- `docs/modules/voice.md`
- `docs/DESIGN_PRINCIPLES.md`
