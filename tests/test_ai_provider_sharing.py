"""Tests for the shared Ollama provider.

EON builds several ``AIManager`` instances — the brain, the memory
store, embeddings, the vision analyser — and each one used to construct
its own ``OllamaProvider``. That is an HTTP client and two model names
per caller, all pointing at the same Ollama server, and it showed up as
a run of identical "Ollama Provider initialized" lines on every launch.

``AIManager`` holds no state of its own, so a manager per caller should
not mean a provider per caller.
"""

from __future__ import annotations

from src.modules.ai.manager import AIManager
from src.modules.ai.provider import OllamaProvider, get_default_provider


def test_managers_share_one_provider():
    first = AIManager()
    second = AIManager()

    assert first._provider is second._provider


def test_the_shared_provider_is_the_default_one():
    assert AIManager()._provider is get_default_provider()


def test_the_default_provider_is_created_once():
    assert get_default_provider() is get_default_provider()


def test_a_provider_can_still_be_passed_in():
    # The escape hatch matters: a caller that wants its own provider
    # (a different host, a different model) still gets one.
    mine = OllamaProvider(model="some-other-model")

    manager = AIManager(provider=mine)

    assert manager._provider is mine
    assert manager._provider is not get_default_provider()


def test_the_manager_still_delegates():
    # Sharing must not have changed what the manager does.
    class _Recording(OllamaProvider):
        def __init__(self) -> None:  # noqa: D107 - no real client needed
            self.seen: list = []

        def chat(self, messages):  # noqa: D102
            self.seen = messages
            return "ok"

    recording = _Recording()
    manager = AIManager(provider=recording)

    assert manager.chat([{"role": "user", "content": "hi"}]) == "ok"
    assert recording.seen == [{"role": "user", "content": "hi"}]
