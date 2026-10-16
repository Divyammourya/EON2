# Conversation Module

## Overview

The Conversation Module manages every interaction between the user and EON.

It serves as the central coordinator for the conversational pipeline, ensuring that each user message passes through perception, memory retrieval, reasoning, planning, and the Brain before a response is returned.

The Conversation Module does not generate responses itself. Instead, it orchestrates the interaction between specialized modules.

---

# Purpose

The Conversation Module is responsible for coordinating the complete lifecycle of a conversation.

Its responsibilities include:

- Receiving user messages
- Updating conversation history
- Invoking perception
- Retrieving relevant memories
- Executing planning and reasoning
- Calling the Brain
- Returning the final response

---

# Responsibilities

The Conversation Module is responsible for:

- Managing conversation flow
- Maintaining short-term conversation history
- Coordinating module execution
- Delivering responses to the user

The Conversation Module is **not** responsible for:

- Memory storage
- Memory retrieval algorithms
- Prompt construction
- Tool execution
- Language model communication

Those responsibilities belong to dedicated modules.

---

# Architecture

```text
                User
                  │
                  ▼
        Conversation Manager
                  │
      ┌───────────┼────────────┐
      ▼           ▼            ▼
 Perception    Recall      Conversation
                               History
      │           │            │
      └───────────┼────────────┘
                  ▼
              Reasoning
                  │
                  ▼
               Planner
                  │
                  ▼
                 Brain
                  │
                  ▼
             Language Model
                  │
                  ▼
          Assistant Response
                  │
                  ▼
       Conversation History
```

---

# Components

## ConversationManager

The ConversationManager coordinates the complete conversation pipeline.

Responsibilities include:

- Receiving user messages
- Updating conversation history
- Calling perception
- Calling recall
- Running reasoning
- Running planning
- Invoking the Brain
- Returning responses

---

## ConversationHistory

ConversationHistory stores recent interactions.

Current responsibilities:

- User messages
- Assistant messages
- Context for the current session

Conversation history is temporary and exists only for the active session.

Permanent knowledge belongs to the Memory Module.

---

# Conversation Pipeline

Each interaction follows this sequence:

1. User sends a message.
2. Perception analyzes the input.
3. Recall searches long-term memory.
4. Reasoning validates the plan.
5. Planner prepares actions.
6. Brain constructs the prompt.
7. AI Manager calls the language model.
8. Response is returned.
9. Conversation history is updated.
10. Store evaluates whether new memories should be saved.

---

# Conversation History

Conversation history represents EON's short-term memory.

It provides conversational continuity during the current session but is not intended for permanent storage.

Long-term knowledge is handled separately by the Memory Module.

---

# Current Implementation

Implemented:

- ConversationManager
- ConversationHistory
- Pipeline orchestration
- Session history
- Memory integration
- Brain integration

---

# Future Improvements

Planned enhancements include:

- Streaming conversations
- Multiple concurrent conversations
- Conversation summarization
- Conversation branching
- Session restoration
- Conversation search
- Conversation export
- Voice conversation support

---

# Design Decisions

Conversation management is intentionally separated from reasoning.

The Conversation Module coordinates the flow of information but does not make intelligent decisions itself.

This separation improves:

- Maintainability
- Scalability
- Testability
- Clear module boundaries

---

# Related Modules

- Brain
- Context
- Perception
- Recall
- Store
- Memory
- Planner
- Reasoning

---

# Related Documentation

- brain.md
- context.md
- memory.md
- recall.md
- PROJECT.md
- architecture/overview.md
