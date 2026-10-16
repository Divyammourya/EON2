# Reasoning Module

## Overview

The Reasoning Module evaluates plans before they are executed.

Its purpose is to ensure that EON does not blindly follow instructions or execute actions without first verifying that they are appropriate.

The Reasoning Module acts as EON's internal decision validator.

---

# Purpose

The Reasoning Module is responsible for determining whether a proposed plan should proceed.

It serves as a safeguard between planning and execution.

Rather than creating plans, it evaluates them.

---

# Responsibilities

The Reasoning Module is responsible for:

- Reviewing generated plans
- Validating proposed actions
- Detecting impossible or unsafe plans
- Approving or rejecting execution
- Producing reasoning results

The Reasoning Module is **not** responsible for:

- Planning
- Tool execution
- Memory retrieval
- Prompt construction
- Language generation

---

# Architecture

```text
          User Request
                │
                ▼
            Planner
                │
                ▼
          Proposed Plan
                │
                ▼
        Reasoning Module
         ┌──────────────┐
         │              │
         ▼              ▼
     Approved       Rejected
         │              │
         ▼              ▼
      Execution      Feedback
```

---

# Components

## ReasoningManager

The ReasoningManager coordinates the reasoning process.

Responsibilities include:

- Receiving plans
- Evaluating feasibility
- Producing reasoning results
- Returning approval status

---

## ReasoningResult

The output of the reasoning process.

A reasoning result contains:

- Approved or rejected status
- Validation message
- Original plan

Other modules use this information before executing actions.

---

# Current Implementation

Implemented:

- ReasoningManager
- ReasoningResult
- Plan approval
- Pipeline integration

Current reasoning is intentionally lightweight and designed for future expansion.

---

# Future Improvements

Planned enhancements include:

- Multi-step logical reasoning
- Safety verification
- Tool permission checks
- Contradiction detection
- Goal consistency analysis
- Cost estimation
- Risk assessment
- Confidence scoring
- Self-verification
- Reflection-based reasoning

---

# Example

User:

```text
Open Visual Studio Code.
```

Planner produces:

```text
Goal:
Open VS Code

Step:
Launch vscode
```

Reasoning evaluates:

- Is the application available?
- Is the action valid?
- Is execution allowed?

Result:

```text
Approved
```

The Execution Module may now proceed.

---

# Design Decisions

Planning and reasoning are intentionally separated.

The Planner decides **what should happen**.

The Reasoning Module decides **whether it should happen**.

This separation improves:

- Safety
- Maintainability
- Testing
- Scalability
- Future autonomous behavior

---

# Relationship with Other Modules

The reasoning pipeline currently follows:

```text
Planner
     │
     ▼
Reasoning
     │
     ▼
Execution
```

This architecture allows new reasoning strategies to be introduced without modifying the Planner or Execution modules.

---

# Related Modules

- Planner
- Execution
- Brain
- Conversation
- Tools

---

# Related Documentation

- planner.md
- conversation.md
- brain.md
- PROJECT.md
- architecture/overview.md
