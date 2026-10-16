"""
Conversation message model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Message:
    """Represents one conversation message."""

    role: str
    content: str
    timestamp: datetime = datetime.now()

    def to_dict(self) -> dict:
        """Convert message into Ollama/OpenAI format."""

        return {
            "role": self.role,
            "content": self.content,
        }
