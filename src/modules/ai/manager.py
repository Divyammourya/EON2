"""
AI Manager.
"""

from __future__ import annotations

from src.modules.ai.provider import OllamaProvider, get_default_provider


class AIManager:
    """
    High-level interface for AI interactions.
    """

    def __init__(
        self,
        provider: OllamaProvider | None = None,
    ) -> None:
        """Configures the manager.

        Args:
            provider: The provider to use. Defaults to the shared one,
                which is what every caller wants: this class adds no
                state of its own, so a manager per caller should not
                mean a provider per caller. EON builds several managers
                (the brain, the memory store, embeddings, the vision
                analyser), and each one used to open its own connection
                to the same Ollama server.
        """
        self._provider = provider or get_default_provider()

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
