# Intent Module

## Overview

The Intent Module is responsible for interpreting the user's request and determining what they want EON to do.

Rather than relying on the language model for every decision, the Intent Module classifies user requests into structured intents that can be processed by the rest of the system.

The Intent Module serves as the first stage of EON's intelligent decision pipeline.

---

# Purpose

The Intent Module transforms natural language into structured intent objects.

Its responsibilities include:

- Understanding user requests
- Identifying user goals
- Extracting execution targets
- Classifying request types

---

# Responsibilities

The Intent Module is responsible for:

- Intent detection
- Request classification
- Target extraction
- Confidence estimation

The Intent Module is **not** responsible for:

- Planning
- Reasoning
- Tool execution
- Memory retrieval
- Prompt generation

---

# Architecture

```text
          User Message
                │
                ▼
      Conversation Manager
                │
                ▼
         Intent Manager
                │
        ┌───────┴────────┐
        ▼                ▼
   Intent Type      Target Object
        │                │
        └───────┬────────┘
                ▼
             Planner
```

---

# Components

## IntentManager

The IntentManager coordinates intent recognition.

Responsibilities include:

- Reading user messages
- Identifying intent type
- Extracting targets
- Returning structured intent objects

---

## Intent

An Intent represents the user's objective.

Every intent contains:

- Type
- Confidence
- Target

Example:

```text
Intent

Type:
Launch

Target:
Visual Studio Code

Confidence:
1.0
```

---

# Intent Pipeline

Every user request follows these steps:

1. Receive user message.
2. Analyze text.
3. Determine intent type.
4. Extract target.
5. Estimate confidence.
6. Return structured intent.

---

# Current Intent Types

Current implementation supports intents such as:

- Chat
- Launch Application

Additional intent types will be introduced as EON evolves.

---

# Example

User:

```text
Open Visual Studio Code.
```

Intent produced:

```text
Type:
Launch

Target:
Visual Studio Code

Confidence:
1.0
```

---

User:

```text
Hello!
```

Intent produced:

```text
Type:
Chat

Confidence:
1.0
```

---

# Current Implementation

Implemented:

- IntentManager
- Intent model
- IntentType enumeration
- Target extraction
- Confidence scoring

Current intent detection uses lightweight rule-based classification.

---

# Future Improvements

Planned enhancements include:

- LLM-assisted intent recognition
- Multi-intent detection
- Entity extraction
- Parameter extraction
- Ambiguity handling
- Follow-up intent resolution
- Context-aware intent recognition
- Intent learning
- Custom intent plugins

---

# Design Decisions

Intent recognition is separated from planning.

The Intent Module answers:

> "What does the user want?"

The Planner answers:

> "How can it be achieved?"

Separating these responsibilities improves:

- Maintainability
- Extensibility
- Testing
- Future AI integration

---

# Relationship with Other Modules

The current decision pipeline is:

```text
Conversation
      │
      ▼
Intent
      │
      ▼
Planner
      │
      ▼
Reasoning
      │
      ▼
Execution
```

---

# Related Modules

- Conversation
- Planner
- Reasoning
- Execution
- Brain

---

# Related Documentation

- conversation.md
- planner.md
- reasoning.md
- execution.md
- brain.md
- PROJECT.md
- architecture/overview.md
