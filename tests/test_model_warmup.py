"""Loading the model at startup instead of mid-conversation.

Measured on EON: the first question after a cold start took 22 seconds,
against 2 for every question after it — and the whole desktop stuttered
while the model was read back in. The fix is to do that read at startup,
where a pause is expected, rather than in the middle of a conversation.

What matters here is that a warm-up can never be worse than not having
one: it asks for a single token, it is a daemon thread, and it never
raises.
"""

from __future__ import annotations

from src.modules.ai.provider import OllamaProvider


class _RecordingClient:
    """Stands in for the Ollama client, and remembers what it was asked."""

    def __init__(self, error: bool = False) -> None:
        self.error = error
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)

        if self.error:
            raise RuntimeError("ollama is not running")

        return {"message": {"content": "hi"}}


def _provider(error: bool = False) -> OllamaProvider:
    provider = OllamaProvider(warm_up_on_start=False)
    provider.client = _RecordingClient(error=error)
    return provider


def test_warming_up_asks_for_exactly_one_token():
    """The work is the load, not the generation."""
    provider = _provider()

    assert provider.warm_up() is True

    call = provider.client.calls[0]
    assert call["options"]["num_predict"] == 1
    assert call["model"] == provider.model


def test_warming_up_pins_the_model_with_keep_alive():
    """Otherwise it is loaded and then immediately unloaded again."""
    provider = _provider()

    provider.warm_up()

    assert provider.client.calls[0]["keep_alive"] == provider.keep_alive


def test_a_failed_warm_up_never_raises():
    """A warm-up that fails is not worse than not having one: the first
    real call pays for the load, which is what used to happen."""
    provider = _provider(error=True)

    assert provider.warm_up() is False


def test_the_warm_up_thread_can_be_turned_off():
    provider = OllamaProvider(warm_up_on_start=False)

    assert provider._warmed_up is False
    assert not any(
        thread.name == "eon-model-warmup" for thread in __import__("threading").enumerate()
    )
