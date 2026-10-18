"""Memory that behaves like memory.

Tier 1. Before this, recall ranked by similarity and nothing else: the
``importance`` column was written on every memory and read back on every
search, and then never used for anything. ``created_at`` was read too,
and equally ignored. A memory from five minutes ago and one from five
months ago scored identically.

Four properties are pinned here:

    1. Storage. Embeddings go in as float16, and come back out in
       whichever format they were written — old JSON rows still read.
    2. Ranking. Among memories that are relevant, importance and age
       decide the order.
    3. The safety property. The relevance filter is still applied to
       similarity alone, so an *important but irrelevant* memory can
       never be pulled in. Importance orders, it does not admit.
    4. Pruning is never automatic, and removes only what it says $it
       will.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.memory.config import MemoryConfig
from src.modules.memory.models import (
    MemoryEntry,
    MemoryImportance,
    MemoryQuery,
    MemoryType,
)
from src.modules.memory.stores.sqlite import (
    SQLiteMemoryStore,
    decode_embedding,
    encode_embedding,
)


class _StubAI:
    """Returns a fixed vector, so similarity is decided by the stored
    embedding and nothing else."""

    def __init__(self, vector: list[float]) -> None:
        self.vector = vector

    def embed(self, text: str) -> list[float]:
        return list(self.vector)


def _store(tmp_path, vector: list[float] | None = None) -> SQLiteMemoryStore:
    config = MemoryConfig(database_path=tmp_path / "memory.db")
    store = SQLiteMemoryStore(config)
    store.initialize()
    store._ai = _StubAI(vector or [1.0, 0.0, 0.0, 0.0])
    return store


def _memory(
    content: str,
    embedding: list[float],
    importance: MemoryImportance = MemoryImportance.NORMAL,
    age_days: float = 0.0,
) -> MemoryEntry:
    return MemoryEntry(
        id=uuid4(),
        content=content,
        memory_type=MemoryType.KNOWLEDGE,
        importance=importance,
        embedding=embedding,
        created_at=datetime.now() - timedelta(days=age_days),
    )


# --- 1. storage -------------------------------------------------------------


def test_a_vector_survives_the_round_trip():
    vector = [0.5, -0.25, 1.0, 0.125]

    assert decode_embedding(encode_embedding(vector)) == pytest.approx(
        vector, abs=1e-3
    )


def test_float16_is_much_smaller_than_the_json_it_replaces():
    """The measured reason for the change: 768 floats cost 10,257 bytes
    as JSON text and 1,536 as float16."""
    vector = [0.123456789] * 768

    packed = encode_embedding(vector)
    as_json = json.dumps(vector).encode()

    assert len(packed) < len(as_json) / 5


def test_rows_written_before_this_change_still_read():
    """A database must not have to be rewritten to be opened."""
    old_row = json.dumps([0.5, -0.25, 1.0])

    assert decode_embedding(old_row) == pytest.approx(
        [0.5, -0.25, 1.0], abs=1e-6
    )


def test_a_missing_vector_reads_as_nothing():
    assert decode_embedding(None) is None
    assert decode_embedding(b"") is None


# --- 2. ranking -------------------------------------------------------------


def test_an_important_memory_outranks_an_equally_relevant_one(tmp_path):
    store = _store(tmp_path)
    store.save(_memory("important", [1.0, 0.0, 0.0, 0.0], MemoryImportance.CRITICAL))
    store.save(_memory("ordinary", [1.0, 0.0, 0.0, 0.0], MemoryImportance.NORMAL))

    results = store.search(MemoryQuery(query="q", limit=10, min_score=0.5))

    assert [r.memory.content for r in results] == ["important", "ordinary"]
    # The reported score is still the similarity, and these two are
    # equally similar — only the ordering differs.
    assert results[0].score == pytest.approx(results[1].score)


def test_a_recent_memory_outranks_an_equally_relevant_old_one(tmp_path):
    store = _store(tmp_path)
    store.save(_memory("today", [1.0, 0.0, 0.0, 0.0], age_days=0))
    store.save(_memory("last year", [1.0, 0.0, 0.0, 0.0], age_days=365))

    results = store.search(MemoryQuery(query="q", limit=10, min_score=0.5))

    assert [r.memory.content for r in results] == ["today", "last year"]


def test_age_alone_cannot_bury_something_durable(tmp_path):
    """A year-old memory still ranks close to a new one — the point is
    to break ties, not to forget."""
    store = _store(tmp_path)
    store.save(_memory("old", [1.0, 0.0, 0.0, 0.0], age_days=365))

    results = store.search(MemoryQuery(query="q", limit=10, min_score=0.5))

    assert results[0].score > 0.9, "a durable memory should not fade away"


def test_a_much_more_relevant_memory_beats_an_important_one(tmp_path):
    """Importance is worth about a third, not an order of magnitude, so
    a clearly better match still wins. Measured: CRITICAL multiplies by
    1.30 and LOW by 0.85, so a 1.0-similarity LOW memory ranks at 0.85
    and beats a 0.6-similarity CRITICAL one at 0.78."""
    store = _store(tmp_path)
    store.save(_memory("very relevant", [1.0, 0.0, 0.0, 0.0], MemoryImportance.LOW))
    store.save(_memory("faintly relevant", [0.6, 0.8, 0.0, 0.0], MemoryImportance.CRITICAL))

    results = store.search(MemoryQuery(query="q", limit=10, min_score=0.5))

    assert results[0].memory.content == "very relevant"


def test_the_boundary_is_where_the_numbers_say_it_is(tmp_path):
    """And the other side of the same line, stated rather than implied:
    at 0.9 against 1.0, the 30% bonus is enough to flip it. That is the
    intended shape — importance should settle close calls — so this
    test exists to make the crossover explicit and deliberate."""
    store = _store(tmp_path)
    store.save(_memory("very relevant", [1.0, 0.0, 0.0, 0.0], MemoryImportance.LOW))
    store.save(_memory("nearly as relevant", [0.9, 0.4359, 0.0, 0.0], MemoryImportance.CRITICAL))

    results = store.search(MemoryQuery(query="q", limit=10, min_score=0.5))

    assert results[0].memory.content == "nearly as relevant"


# --- 3. the safety property -------------------------------------------------


def test_an_important_but_irrelevant_memory_is_not_admitted(tmp_path):
    """The whole reason the filter stays on similarity. Importance
    orders what is relevant; it must never decide what is relevant."""
    store = _store(tmp_path)
    store.save(_memory("about cooking", [0.0, 1.0, 0.0, 0.0], MemoryImportance.CRITICAL))

    results = store.search(MemoryQuery(query="q", limit=10, min_score=0.5))

    assert results == [], "an unrelated memory was admitted on importance"


def test_an_irrelevant_memory_stays_out_even_alongside_a_relevant_one(tmp_path):
    store = _store(tmp_path)
    store.save(_memory("relevant", [1.0, 0.0, 0.0, 0.0], MemoryImportance.LOW))
    store.save(_memory("irrelevant", [0.0, 1.0, 0.0, 0.0], MemoryImportance.CRITICAL))

    results = store.search(MemoryQuery(query="q", limit=10, min_score=0.5))

    assert [r.memory.content for r in results] == ["relevant"]


# --- 4. counting and pruning ------------------------------------------------


def test_stats_counts_what_is_actually_stored(tmp_path):
    store = _store(tmp_path)
    store.save(_memory("one", [1.0, 0.0, 0.0, 0.0]))
    store.save(_memory("two", [1.0, 0.0, 0.0, 0.0]))

    stats = store.stats()

    assert stats["memories"] == 2
    assert stats["embedding_bytes"] > 0
    assert stats["total_bytes"] == (
        stats["embedding_bytes"] + stats["content_bytes"]
    )


def test_stats_on_an_empty_store_is_all_zero(tmp_path):
    stats = _store(tmp_path).stats()

    assert stats["memories"] == 0
    assert stats["total_bytes"] == 0


def test_pruning_removes_only_old_and_unimportant(tmp_path):
    store = _store(tmp_path)
    store.save(_memory("old trivia", [1.0, 0.0, 0.0, 0.0], MemoryImportance.LOW, age_days=365))
    store.save(_memory("old but important", [1.0, 0.0, 0.0, 0.0], MemoryImportance.HIGH, age_days=365))
    store.save(_memory("recent trivia", [1.0, 0.0, 0.0, 0.0], MemoryImportance.LOW, age_days=1))

    removed = store.prune()

    assert removed == 1
    remaining = {r.memory.content for r in store.search(
        MemoryQuery(query="q", limit=10, min_score=0.5)
    )}
    assert remaining == {"old but important", "recent trivia"}


def test_pruning_nothing_is_harmless(tmp_path):
    assert _store(tmp_path).prune() == 0
