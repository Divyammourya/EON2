"""
Context models.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Context:
    """
    Represents the current conversational context.
    """

    topic: str = ""

    entities: list[str] = field(default_factory=list)

    last_user_message: str = ""

    last_assistant_message: str = ""
