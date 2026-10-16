# Naming Conventions

## Purpose

This document defines the naming conventions used throughout the EON project.

Consistent naming improves readability, maintainability, discoverability, and long-term code quality.

---

# General Principles

Names should be:

- Clear
- Descriptive
- Consistent
- Unambiguous
- Pronounceable

Avoid abbreviations unless they are widely recognized.

Prefer readability over brevity.

---

# Project Structure

## Packages

Use lowercase names.

Examples:

```text
voice
memory
llm
storage
plugins
utils
exceptions
providers
```

---

## Modules

Use lowercase snake_case.

Examples:

```text
voice_manager.py
provider_registry.py
conversation_manager.py
session_store.py
memory_provider.py
```

---

## Classes

Use PascalCase.

Examples:

```python
VoiceManager
OpenAIProvider
MemoryProvider
ConversationSession
ProviderRegistry
PluginLoader
```

Class names should represent nouns or entities.

---

## Abstract Classes

Abstract classes should describe capabilities rather than implementations.

Examples:

```python
VoiceProvider
SpeechToTextProvider
TextToSpeechProvider
MemoryProvider
StorageProvider
Plugin
```

Avoid implementation-specific names.

---

## Interfaces

Interfaces follow the same naming convention as abstract classes.

Examples:

```python
Provider
MemoryProvider
StorageProvider
Tool
Plugin
```

---

## Functions

Use snake_case.

Examples:

```python
start_session()
load_provider()
create_request()
register_plugin()
transcribe_audio()
```

Function names should begin with a verb.

---

## Methods

Use snake_case.

Examples:

```python
initialize()
shutdown()
health_check()
speak()
transcribe()
```

Method names should describe the action performed.

---

## Variables

Use snake_case.

Examples:

```python
session_id
audio_bytes
provider_name
request_id
language_code
```

Variable names should clearly describe their contents.

---

## Constants

Use UPPER_SNAKE_CASE.

Examples:

```python
DEFAULT_TIMEOUT
MAX_RETRY_COUNT
_AUDIO_METADATA_KEY
DEFAULT_LANGUAGE
```

Module-level constants should always use uppercase.

---

## Private Members

Prefix internal members with a single underscore.

Examples:

```python
_client
_voice
_provider_registry
_session_store
```

Private members should not be accessed outside their owning class.

---

## Type Aliases

Use PascalCase.

Examples:

```python
ProviderMap
SessionId
PluginName
LanguageCode
```

---

## Enumerations

Use PascalCase for the enum and UPPER_SNAKE_CASE for members.

Example:

```python
class SessionState(Enum):
    CREATED = auto()
    ACTIVE = auto()
    CLOSED = auto()
```

---

## Exceptions

Exception classes should end with `Error`.

Examples:

```python
VoiceProviderError
MemoryError
PluginError
StorageError
```

Exception names should clearly describe the failure.

---

## Files

Use lowercase snake_case.

Examples:

```text
voice_manager.py
provider_registry.py
conversation_manager.py
plugin_loader.py
```

Avoid spaces and hyphens in Python filenames.

---

## Documentation Files

Documentation uses lowercase names where practical.

Examples:

```text
overview.md
voice.md
memory.md
coding.md
testing.md
```

Project-level documents may remain uppercase for visibility.

Examples:

```text
README.md
ROADMAP.md
VISION.md
STATUS.md
```

---

## Branches

Use lowercase with descriptive prefixes.

Examples:

```text
feature/voice-manager
fix/session-lifecycle
refactor/provider-registry
docs/architecture
test/memory-module
```

---

## Commits

Use the imperative mood.

Examples:

```text
Add provider registry
Implement memory interface
Refactor voice manager
Update architecture documentation
```

---

# Naming Guidelines

Prefer:

```text
conversation_manager
```

Instead of:

```text
conv_mgr
```

Prefer:

```text
provider_registry
```

Instead of:

```text
registry2
```

Names should communicate intent without requiring additional explanation.

---

# Consistency

Once a naming pattern has been established, it should be followed throughout the project.

Avoid introducing multiple names for the same concept.

For example, use one consistent term such as:

- Provider
- Session
- Manager
- Registry
- Configuration

rather than mixing synonyms across modules.

---

# Related Documentation

- `DESIGN_PRINCIPLES.md`
- `guides/coding.md`
- `PROJECT.md`
- `architecture/components.md`
