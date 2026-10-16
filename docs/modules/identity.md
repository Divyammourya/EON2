# Identity Module

The Identity Module defines who EON is.

Unlike traditional chatbots that rely on hardcoded prompts, EON generates its identity dynamically through a dedicated module. This ensures that every conversation begins with a consistent understanding of who EON is, who created it, what it can do, and how it should behave.

---

# Purpose

The Identity Module acts as the single source of truth for EON's identity.

Its responsibilities include:

- Defining EON's identity
- Defining EON's creator
- Defining EON's capabilities
- Building the system prompt
- Preventing identity hallucinations
- Providing a centralized identity API

Every component that needs identity information retrieves it from this module rather than hardcoding values.

---

# Responsibilities

The Identity Module is responsible for:

- Identity management
- Personality definition
- Capability descriptions
- System prompt generation
- Creator information
- Version information
- Runtime description

It is **not** responsible for memory, reasoning, planning, or tool execution.

---

# Architecture

```
                 Brain
                   │
                   ▼
           Context Builder
                   │
                   ▼
          IdentityManager
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
 IdentityProfile        Capabilities
                   │
                   ▼
            System Prompt
                   │
                   ▼
                 LLM
```

---

# Components

## IdentityProfile

Stores static identity information.

Examples include:

- Name
- Creator
- Version
- Description
- Company
- Runtime location

IdentityProfile contains no logic.

---

## Capability

Represents a single capability that EON possesses.

Each capability includes:

- Name
- Description

Example:

```
Memory
Remember important long-term information.
```

---

## IdentityManager

The central service of the Identity Module.

Responsibilities include:

- Managing the identity profile
- Managing capabilities
- Building the system prompt
- Providing identity information to other modules

The IdentityManager is injected into the Brain during application startup.

---

# Data Flow

```
Application Startup

↓

IdentityProfile created

↓

IdentityManager initialized

↓

Brain receives IdentityManager

↓

ContextBuilder requests system prompt

↓

IdentityManager generates prompt

↓

Prompt sent to LLM
```

---

# Lifecycle

1. Application starts.
2. IdentityManager is created.
3. IdentityProfile is loaded.
4. Capabilities are registered.
5. Brain receives IdentityManager.
6. Every conversation uses the generated system prompt.

The identity remains constant for the lifetime of the application.

---

# Public API

## system_prompt()

Builds the complete system prompt used by the LLM.

---

## capability_prompt()

Generates a formatted list of EON's capabilities.

---

# Current Implementation

Implemented:

- IdentityProfile
- IdentityManager
- Capability model
- Dynamic system prompt generation
- Creator protection
- Capability injection
- Brain integration
- ContextBuilder integration

---

# Future Improvements

Planned features include:

- Personality profiles
- Mood system
- Mission statement
- Core values
- Runtime configuration
- Identity persistence
- Multiple identities
- Custom user-defined identities
- Voice personality integration

---

# Design Decisions

The Identity Module exists to eliminate duplicated prompt engineering.

Instead of embedding identity information directly inside prompt templates, all identity information is generated dynamically.

This approach provides:

- Better maintainability
- Single source of truth
- Easier customization
- Cleaner architecture
- Consistent responses

---

# Related Modules

- Brain
- Context
- Conversation
- Memory

---

# Related Documentation

- PROJECT.md
- CHANGELOG.md
- architecture/overview.md
- architecture/components.md
