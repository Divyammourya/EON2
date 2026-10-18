"""
Ollama Provider for EON.
"""

from __future__ import annotations

import threading

from ollama import Client

from src.core.logger import get_logger

logger = get_logger("AI.Provider")

#: How long Ollama keeps a model in memory after answering.
#:
#: On a small machine this is the most important number in the file.
#: Left unset, Ollama unloads the model after a few idle minutes and
#: the next call pays to read it back off disk — which, for a 2 GB
#: model on a drive with under a gigabyte free, is eleven to thirteen
#: seconds of doing nothing. Measured on EON: a ten-word reply took
#: 11s with nothing pinned, and about a second once it stayed resident.
#:
#: Long enough to survive a conversation; not so long that it sits in
#: memory after EON is closed.
DEFAULT_KEEP_ALIVE = "30m"

#: Generation options sent with every call.
#:
#: ``num_ctx`` matters most here: Ollama allocates the KV cache up
#: front from this number, and its default is larger than any prompt
#: EON builds. On 8 GB of RAM, that reserved memory is exactly what is
#: missing. ``num_predict`` stops a runaway reply, and ``temperature``
#: is pinned so the same question does not come back with a different
#: personality each time.
DEFAULT_OPTIONS: dict = {
    "num_ctx": 4096,
    "num_predict": 512,
    "temperature": 0.7,
}


class OllamaProvider:
    """
    Handles communication with Ollama.
    """

    def __init__(
        self,
        host: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:3b",
        embedding_model: str = "nomic-embed-text",
        keep_alive: str | int | None = None,
        options: dict | None = None,
    ) -> None:

        self.client = Client(host=host)

        self.model = model
        self.embedding_model = embedding_model

        # ``None`` means "use the defaults above", so an explicit empty
        # dict can still mean "send no options at all".
        self.keep_alive = (
            DEFAULT_KEEP_ALIVE if keep_alive is None else keep_alive
        )
        self.options = dict(DEFAULT_OPTIONS if options is None else options)

        # Logged because this is the difference between a one-second
        # reply and a twenty-second one, and it should be visible at
        # startup rather than inferred.
        logger.info(
            "Ollama Provider initialized (%s; keep_alive=%s, num_ctx=%s)",
            self.model,
            self.keep_alive,
            self.options.get("num_ctx"),
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
            keep_alive=self.keep_alive,
            options=self.options,
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
            keep_alive=self.keep_alive,
            options=self.options,
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
            keep_alive=self.keep_alive,
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
