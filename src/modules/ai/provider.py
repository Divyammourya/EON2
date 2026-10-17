"""
Ollama Provider for EON.
"""

from __future__ import annotations

import threading

from ollama import Client

from src.core.logger import get_logger

logger = get_logger("AI.Provider")


class OllamaProvider:
    """
    Handles communication with Ollama.
    """

    def __init__(
        self,
        host: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:3b",
        embedding_model: str = "nomic-embed-text",
    ) -> None:

        self.client = Client(host=host)

        self.model = model
        self.embedding_model = embedding_model

        logger.info(
            "Ollama Provider initialized (%s)",
            self.model,
        )

    def chat(
        self,
        messages: list[dict],
    ) -> str:
        """
        Send a conversation to the language model.
        """

        response = self.client.chat(
            model=self.model,
            messages=messages,
        )

        return response["message"]["content"]

    def chat_stream(
        self,
        messages: list[dict],
    ):
        """
        Send a conversation to the language model, yielding the reply
        as incremental text deltas instead of waiting for it in full.
        """

        stream = self.client.chat(
            model=self.model,
            messages=messages,
            stream=True,
        )

        for chunk in stream:
            content = chunk["message"]["content"]

            if content:
                yield content

    def chat_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        model: str | None = None,
    ) -> str:
        """
        Send a single-turn prompt plus an image to a vision-capable
        model.

        Kept separate from ``chat`` rather than overloading it with an
        optional ``images`` param — this is deliberately single-turn
        (no conversation history) since vision queries in EON are
        always "here's what the screen looks like right now", not an
        ongoing multimodal conversation.

        Args:
            prompt: The question/instruction for the model.
            image_bytes: Encoded image data (e.g. JPEG bytes).
            model: Override the model to use for this call. Needed
                because ``self.model`` (the default chat model, e.g.
                ``qwen2.5:3b``) is very likely not vision-capable —
                callers should pass a vision model such as ``"llava"``.
        """

        response = self.client.chat(
            model=model or self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_bytes],
                }
            ],
        )

        return response["message"]["content"]

    def embed(
        self,
        text: str,
    ) -> list[float]:
        """
        Generate an embedding for text.
        """

        response = self.client.embed(
            model=self.embedding_model,
            input=text,
        )

        return response["embeddings"][0]


# The provider every AIManager shares unless one is passed in explicitly.
_default_provider: "OllamaProvider | None" = None
_default_provider_lock = threading.Lock()


def get_default_provider() -> OllamaProvider:
    """The shared provider, created once on first use.

    Ollama serves a single copy of the model, and an ``OllamaProvider``
    is only an HTTP client plus two model names — so a provider *per
    caller* buys nothing. It re-reads the same configuration and opens
    another connection to the same server. EON builds several (the
    brain, the memory store, embeddings, the vision analyser), which
    showed up as a run of identical "Ollama Provider initialized"
    lines on every launch.

    Sharing is safe because the provider holds no conversation state:
    every call passes its own messages.

    Returns:
        The process-wide provider.
    """
    global _default_provider

    if _default_provider is None:
        with _default_provider_lock:
            # Re-check inside the lock: two threads can both get past
            # the check above before either takes the lock.
            if _default_provider is None:
                _default_provider = OllamaProvider()

    return _default_provider
