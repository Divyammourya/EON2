"""How relevant a memory has to be before EON recalls it.

This was hardcoded in the SQLite store as ``if score > 0.30``, with
``# if score > 0.55:`` left commented out directly above it. Against
this embedding model, *unrelated* text scores around 0.3–0.5, so 0.30
let almost anything through — and recalled memories are passed into the
brain as part of the prompt, so an irrelevant one does not just clutter
the log, it changes the answer.

In practice EON recalled the same unrelated memory (a note about
spelling asterisks) on every single turn, at 0.312, 0.410 and 0.469 for
three different topics.

The bar is now a setting, ``memory_recall_min_score``, defaulting to
the 0.55 the code itself said was intended.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.modules.memory.config import MemoryConfig
from src.modules.memory.models import (
    DEFAULT_MIN_SCORE,
    MemoryEntry,
    MemoryQuery,
    MemoryType,
)
from src.modules.memory.stores.sqlite import SQLiteMemoryStore
from src.modules.recall.manager import RecallManager
from src.modules.recall.recall import RecallEngine


# --- the default ------------------------------------------------------------


def test_the_default_bar_is_the_value_the_code_intended():
    assert DEFAULT_MIN_SCORE == 0.55
    assert MemoryQuery(query="anything").min_score == 0.55


def test_a_query_can_choose_its_own_bar():
    assert MemoryQuery(query="anything", min_score=0.9).min_score == 0.9


# --- the plumbing: the bar reaches the store ---------------------------------


class _RecordingMemory:
    """Stands in for the memory service, recording the query it got."""

    def __init__(self) -> None:
        self.queries: list[MemoryQuery] = []

    def search(self, query: MemoryQuery):
        self.queries.append(query)
        return []


class _Context:
    def __init__(self, topic: str) -> None:
        self.topic = topic


def test_the_engine_passes_its_bar_into_the_query():
    memory = _RecordingMemory()
    engine = RecallEngine(memory=memory, min_score=0.8)

    engine.recall(_Context("coding"))

    assert memory.queries[0].query == "coding"
    assert memory.queries[0].min_score == 0.8


def test_the_engine_defaults_to_the_intended_bar():
    memory = _RecordingMemory()

    RecallEngine(memory=memory).recall(_Context("coding"))

    assert memory.queries[0].min_score == DEFAULT_MIN_SCORE


def test_the_manager_passes_the_bar_through():
    memory = _RecordingMemory()
    manager = RecallManager(memory=memory, min_score=0.7)

    manager.recall(_Context("coding"))

    assert memory.queries[0].min_score == 0.7


# --- the store actually applies it -------------------------------------------


class _StubAI:
    """Returns a fixed embedding, so scores are predictable."""

    def __init__(self, vector: list[float]) -> None:
        self.vector = vector

    def embed(self, text: str) -> list[float]:
        return self.vector


@pytest.fixture
def store(tmp_path: Path):
    """A real store holding one matching and one unrelated memory."""
    s = SQLiteMemoryStore(MemoryConfig(database_path=tmp_path / "memory.db"))
    s.initialize()

    query_vector = [1.0, 0.0, 0.0]
    # Identical to the query vector -> cosine 1.0.
    s.save(
        MemoryEntry(
            content="the relevant one",
            memory_type=MemoryType.KNOWLEDGE,
            embedding=list(query_vector),
        )
    )
    # Orthogonal to it -> cosine 0.0.
    s.save(
        MemoryEntry(
            content="the unrelated one",
            memory_type=MemoryType.KNOWLEDGE,
            embedding=[0.0, 1.0, 0.0],
        )
    )

    # The store builds its own AIManager; swap in a predictable one.
    s._ai = _StubAI(query_vector)

    yield s

    s.shutdown()


def test_a_high_bar_keeps_only_the_relevant_memory(store):
    results = store.search(MemoryQuery(query="q", min_score=0.55))

    assert [r.memory.content for r in results] == ["the relevant one"]


def test_a_low_bar_lets_the_unrelated_one_through(store):
    # The old behaviour, kept here as the reason this matters: at 0.30
    # the unrelated memory comes back too. (Below zero, because the
    # comparison is strict and the orthogonal memory scores exactly 0.0.)
    results = store.search(MemoryQuery(query="q", min_score=-1.0))

    assert {r.memory.content for r in results} == {
        "the relevant one",
        "the unrelated one",
    }


def test_the_score_is_still_reported(store):
    results = store.search(MemoryQuery(query="q", min_score=0.55))

    assert results[0].score == pytest.approx(1.0)


def test_the_bar_is_per_query(store):
    # Above any possible cosine similarity, so nothing qualifies; and
    # low enough that everything does.
    high = store.search(MemoryQuery(query="q", min_score=1.5))
    low = store.search(MemoryQuery(query="q", min_score=-1.0))

    assert len(high) == 0
    assert len(low) == 2
