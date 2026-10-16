"""
AI Manager.
"""

from __future__ import annotations

from src.modules.ai.provider import OllamaProvider


class AIManager:
    """
    High-level interface for AI interactions.
    """

    def __init__(self) -> None:
        self._provider = OllamaProvider()

    def chat(
        self,
        messages: list[dict],
    ) -> str:
        return self._provider.chat(messages)

    def chat_stream(
        self,
        messages: list[dict],
    ):
        return self._provider.chat_stream(messages)

    def embed(
        self,
        text: str,
    ) -> list[float]:
        return self._provider.embed(text)

    def chat_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        model: str | None = None,
    ) -> str:
        return self._provider.chat_with_image(
            prompt,
            image_bytes,
            model=model,
        )
