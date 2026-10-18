"""What a turn costs, and what it must not.

EON's own log gave the real numbers: the embed took a second, and each of
two chat calls took eleven to thirteen seconds to produce about ten words.
Neither is a hardware limit, and both are pinned here.

    1. The tool router fires on every message the keyword rules miss —
       which is most conversation. Asking the model about "hi" can only
       ever come back "no tool", and it cost eleven seconds. So obvious
       conversation never reaches the model.

    2. Every call to Ollama was sent with nothing pinned: no keep_alive,
       no num_ctx. That left Ollama free to unload a 2 GB model between
       turns and pay to read it back off a disk with under a gigabyte
       free — which is what twenty seconds actually looked like.

Both are cost properties, so both are tested as such: not "does it work"
but "how many times is the expensive thing touched".
"""

from __future__ import annotations

import pytest

from src.modules.ai.provider import (
    DEFAULT_KEEP_ALIVE,
    DEFAULT_OPTIONS,
    OllamaProvider,
)
from src.modules.intent.models import IntentType
from src.modules.intent.tool_router import ToolRouter


class _CountingAI:
    """Records how often it was asked, and answers with a fixed reply."""

    def __init__(self, reply: str = "none") -> None:
        self.reply = reply
        self.calls = 0

    def chat(self, messages: list[dict]) -> str:
        self.calls += 1
        return self.reply


# --- 1. the router must not spend a model call on conversation -------------


@pytest.mark.parametrize(
    "message",
    [
        "hi",
        "Hi!",
        "hello",
        "hey",
        "thanks",
        "thank you",
        "ok",
        "okay",
        "cool",
        "good morning",
        "how are you",
        "what's your name",
        "bye",
        "",
        "   ",
    ],
)
def test_conversation_never_reaches_the_model(message):
    ai = _CountingAI()
    router = ToolRouter(ai=ai, enabled=True)

    assert router.choose(message) is None
    assert ai.calls == 0, f"{message!r} cost a model call"


@pytest.mark.parametrize(
    "message",
    [
        "do I need an umbrella today",
        "is my screen too bright",
        "why is the sky blue",
        "could you put milk on my shopping list",
        "what?",
        "is that true",
        # Short, and still requests. An earlier version of the filter
        # skipped messages by word count and dropped all three of these
        # — which is exactly what the router exists to catch.
        "start notepad",
        "screenshot",
        "volume up",
    ],
)
def test_a_real_request_still_reaches_the_model(message):
    """The router's whole purpose — it must not be filtered away."""
    ai = _CountingAI(reply="none")
    router = ToolRouter(ai=ai, enabled=True)

    router.choose(message)

    assert ai.calls == 1, f"{message!r} was never asked about"


def test_a_chosen_tool_still_comes_back():
    """The filter must not have broken the thing it was protecting."""
    ai = _CountingAI(reply="weather")
    router = ToolRouter(ai=ai, enabled=True)

    intent = router.choose("do I need an umbrella today")

    assert intent is not None
    assert intent.type is IntentType.WEATHER


def test_the_model_is_asked_at_most_once_per_message():
    ai = _CountingAI()
    router = ToolRouter(ai=ai, enabled=True)

    router.choose("hi")
    router.choose("do I need an umbrella today")
    router.choose("thanks")

    assert ai.calls == 1


# --- 2. nothing goes to Ollama unpinned ------------------------------------


class _RecordingClient:
    """Stands in for ``ollama.Client`` and keeps every call's kwargs."""

    def __init__(self, stream_chunks: int = 2) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._stream_chunks = stream_chunks

    def chat(self, **kwargs):
        self.calls.append(("chat", kwargs))

        if kwargs.get("stream"):
            return (
                {"message": {"content": f"chunk{index}"}}
                for index in range(self._stream_chunks)
            )

        return {"message": {"content": "hello"}}

    def embed(self, **kwargs):
        self.calls.append(("embed", kwargs))
        return {"embeddings": [[0.0, 1.0]]}


def _provider() -> tuple[OllamaProvider, _RecordingClient]:
    provider = OllamaProvider()
    client = _RecordingClient()
    provider.client = client
    return provider, client


def test_chat_pins_keep_alive_and_options():
    provider, client = _provider()

    provider.chat([{"role": "user", "content": "hi"}])

    _, kwargs = client.calls[0]
    assert kwargs["keep_alive"] == DEFAULT_KEEP_ALIVE
    assert kwargs["options"]["num_ctx"] == DEFAULT_OPTIONS["num_ctx"]


def test_streaming_chat_pins_them_too():
    provider, client = _provider()

    list(provider.chat_stream([{"role": "user", "content": "hi"}]))

    _, kwargs = client.calls[0]
    assert kwargs["keep_alive"] == DEFAULT_KEEP_ALIVE
    assert kwargs["options"]


def test_embed_pins_keep_alive_so_it_cannot_evict_the_chat_model():
    """The embedding model is loaded on every recall. If loading it
    evicts the chat model, the next chat call pays for the reload — so
    the same residency policy has to apply to both."""
    provider, client = _provider()

    provider.embed("hi")

    _, kwargs = client.calls[0]
    assert kwargs["keep_alive"] == DEFAULT_KEEP_ALIVE


def test_the_defaults_are_real_values_not_placeholders():
    assert DEFAULT_KEEP_ALIVE
    assert DEFAULT_OPTIONS["num_ctx"] > 0
    assert DEFAULT_OPTIONS["num_predict"] > 0


def test_explicit_options_win():
    provider = OllamaProvider(options={"num_ctx": 8192})

    assert provider.options == {"num_ctx": 8192}


def test_an_explicit_empty_dict_still_means_no_options():
    """So "send nothing" remains expressible."""
    provider = OllamaProvider(options={})

    assert provider.options == {}
    assert provider.keep_alive == DEFAULT_KEEP_ALIVE
