# System Diagrams

## Purpose

This document contains high-level diagrams illustrating the architecture of EON.

These diagrams provide a visual overview of module relationships, dependency flow, and system organization.

---

# Overall System Architecture

```text
                     User
                       │
                       ▼
                Application Layer
                       │
      ┌────────────────┼────────────────┐
      │                │                │
      ▼                ▼                ▼
 Voice Module     Memory Module     LLM Module
      │                │                │
      └────────────────┼────────────────┘
                       │
                       ▼
                Plugin Manager
                       │
                       ▼
                 Storage Layer
```

---

# Dependency Direction

```text
Application

↓

Managers

↓

Interfaces

↓

Providers

↓

Third-Party Libraries
```

Dependencies always point toward abstractions.

---

# Provider Pattern

```text
                VoiceProvider
                     ▲
      ┌──────────────┼──────────────┐
      │              │              │
      │              │              │
PiperProvider  FasterWhisperProvider  OpenAIProvider
```

Only provider implementations depend on third-party SDKs.

---

# Voice Module

```text
Speech Request

↓

VoiceManager

↓

VoiceProvider

↓

Concrete Provider

↓

Speech Result
```

---

# Memory Module

```text
Conversation

↓

Embedding Provider

↓

Vector Storage

↓

Retrieved Memory

↓

LLM Context
```

---

# LLM Module

```text
Prompt Builder

↓

LLM Provider

↓

Language Model

↓

Structured Response
```

---

# Plugin System

```text
Application

↓

Plugin Manager

↓

Plugin Registry

↓

Loaded Plugins
```

---

# Storage Layer

```text
Application

↓

Repository

↓

Storage Provider

↓

Database
```

---

# Future Architecture

```text
                 Application
                      │
      ┌───────────────┼────────────────┐
      │               │                │
      ▼               ▼                ▼
   Voice          Memory            LLM
      │               │                │
      └───────────────┼────────────────┘
                      ▼
                Agent Framework
                      ▼
                Plugin System
                      ▼
                Storage Layer
```

---

# Related Documents

- overview.md
- components.md
- voice.md
- memory.md
- llm.md
- plugins.md
- storage.md
