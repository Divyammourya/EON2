"""
Memory Extractor.
"""

from __future__ import annotations


class MemoryExtractor:
    """
    Converts user messages into canonical long-term memories.
    """

    def extract(
        self,
        text: str,
    ) -> str:

        lower = text.lower()

        if lower.startswith("my name is "):
            name = text[11:].strip().rstrip(".")
            return f"User's name is {name}."

        if lower.startswith("i like "):
            thing = text[7:].strip().rstrip(".")
            return f"User likes {thing}."

        if lower.startswith("i love "):
            thing = text[7:].strip().rstrip(".")
            return f"User loves {thing}."

        if lower.startswith("i prefer "):
            thing = text[9:].strip().rstrip(".")
            return f"User prefers {thing}."

        if lower.startswith("remember that i prefer "):
            thing = text[23:].strip().rstrip(".")
            return f"User prefers {thing}."

        return text
