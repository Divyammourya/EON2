"""
SQLite Memory Store.

SQLite implementation of the MemoryStore interface.
"""

from __future__ import annotations

import json
import math
import struct
import threading

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from uuid import UUID

from src.core.logger import get_logger
from src.modules.memory.config import MemoryConfig
from src.modules.memory.models import (
    MemoryEntry,
    MemoryImportance,
    MemoryQuery,
    MemorySearchResult,
    MemoryType,
)
from src.modules.memory.store import MemoryStore

from src.modules.ai.manager import AIManager
from src.modules.memory.vector import cosine_similarity

logger = get_logger("SQLiteMemoryStore")


def encode_embedding(vector: list[float] | None) -> bytes | None:
    """Packs a vector for storage.

    Stored as float16 rather than JSON text. Measured against EON's own
    database: 768 floats cost 10,257 bytes as JSON and 1,536 as float16
    — six times the room on the same disk, and the difference is
    immaterial for a cosine comparison. Half precision resolves about
    three decimal places, which is finer than the gaps between memories
    EON actually tells apart.
    """
    if vector is None:
        return None

    return struct.pack(f"<{len(vector)}e", *vector)


def decode_embedding(raw: bytes | str | None) -> list[float] | None:
    """Reads a vector back, in whichever format it was written.

    Rows stored before this change hold JSON text. Both are accepted
    rather than migrated: an existing database can be read without being
    rewritten, and old rows age out on their own.
    """
    if raw is None:
        return None

    if isinstance(raw, (bytes, bytearray, memoryview)):
        buffer = bytes(raw)

        if not buffer:
            return None

        return list(struct.unpack(f"<{len(buffer) // 2}e", buffer))

    return json.loads(raw)


#: How far importance can shift a memory's ranking. The relevance filter
#: is still applied to similarity alone — importance must never be able
#: to pull in something irrelevant — so this only decides the order
#: among memories that were relevant anyway. Deliberately gentle: a
#: CRITICAL memory outranks a NORMAL one by about a third.
_IMPORTANCE_STEP = 0.15

#: And how much being recent helps. A memory from today ranks about 19%
#: above one from a year ago.
_RECENCY_FLOOR = 0.9
_RECENCY_RANGE = 0.2


class SQLiteMemoryStore(MemoryStore):
    """
    SQLite-backed implementation of the MemoryStore interface.
    """

    def __init__(
        self,
        config: MemoryConfig,
    ) -> None:
        self._config = config
        self._connection: sqlite3.Connection | None = None
        self._ai = AIManager()
        # The engine can call into the store from multiple threads
        # (e.g. main console thread + wake-word listener thread), so we
        # need a lock to serialize access to the single shared connection.
        self._lock = threading.Lock()

    def initialize(self) -> None:
        """
        Initialize the SQLite database.
        """
        database = Path(self._config.database_path)

        database.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # check_same_thread=False: EON calls into this store from more than
        # one thread (main loop + wake-word callback thread). We serialize
        # actual access with self._lock instead, which is the safe way to
        # share one sqlite3.Connection across threads.
        self._connection = sqlite3.connect(
            database,
            check_same_thread=False,
        )

        self._connection.row_factory = sqlite3.Row

        self._create_schema()

        logger.info(
            "SQLite Memory Store initialized."
        )

    def shutdown(self) -> None:
        """
        Close the database connection.
        """
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

        logger.info(
            "SQLite Memory Store shutdown."
        )

    def _create_schema(self) -> None:
        """
        Create the memory table if it does not exist.
        """
        assert self._connection is not None

        cursor = self._connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                importance INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT,
                created_at TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
            """
        )

        # Learned-phrase dictionary: maps a normalized raw phrase the
        # user actually said/typed straight to the intent/action it
        # should route to. This is a simple lookup table, not any form
        # of speech-model personalization — see
        # SQLiteMemoryStore.set_learned_phrase for the honest framing.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS learned_phrases (
                raw_phrase TEXT PRIMARY KEY,
                intent_type TEXT NOT NULL,
                target TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        self._connection.commit()

    def save(
        self,
        memory: MemoryEntry,
    ) -> None:
        """
        Save a memory into SQLite.
        """

        assert self._connection is not None

        self._lock.acquire()
        try:
            self._connection.execute(
                """
                INSERT INTO memories (
                    id,
                    type,
                    importance,
                    content,
                    embedding,
                    created_at,
                    metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(memory.id),
                    memory.memory_type.value,
                    memory.importance.value,
                    memory.content,
                    encode_embedding(memory.embedding),
                    memory.created_at.isoformat(),
                    "{}",
                ),
            )

            self._connection.commit()
        finally:
            self._lock.release()

    def update(
        self,
        memory: MemoryEntry,
    ) -> None:
        raise NotImplementedError

    def delete(
        self,
        memory_id: UUID,
    ) -> None:
        raise NotImplementedError

    def get(
        self,
        memory_id: UUID,
    ) -> MemoryEntry | None:
        raise NotImplementedError


    def search(
        self,
        query: MemoryQuery,
    ) -> list[MemorySearchResult]:
        """
        Semantic vector search.
        """

        assert self._connection is not None

        query_embedding = self._ai.embed(query.query)

        # The query vector is compared against every stored memory, so
        # its norm is constant for the whole scan — compute it once here
        # instead of recomputing it N times inside cosine_similarity.
        query_norm = math.sqrt(sum(x * x for x in query_embedding))

        self._lock.acquire()
        try:
            cursor = self._connection.execute(
                """
                SELECT
                    id,
                    type,
                    importance,
                    content,
                    embedding,
                    created_at
                FROM memories
                """
            )

            rows = cursor.fetchall()
        finally:
            self._lock.release()

        results: list[MemorySearchResult] = []
        rankings: list[float] = []

        for row in rows:

            if row["embedding"] is None:
                continue

            embedding = decode_embedding(row["embedding"])

            if embedding is None:
                continue

            score = cosine_similarity(
                query_embedding,
                embedding,
                norm_a=query_norm,
            )

            logger.debug(
                "Memory candidate: %r -> score=%.3f",
                row["content"],
                score,
            )

            memory = MemoryEntry(
                id=UUID(row["id"]),
                content=row["content"],
                memory_type=MemoryType(row["type"]),
                importance=MemoryImportance(row["importance"]),
                embedding=embedding,
                created_at=datetime.fromisoformat(
                    row["created_at"]
                ),
            )

            # Filtered in on similarity alone, so nothing irrelevant
            # can arrive on the strength of being important. Only once
            # it is in does importance and age decide the order.
            if score <= query.min_score:
                continue

            # ``score`` stays the raw cosine similarity, because that is
            # the number callers and the console already understand, and
            # what ``min_score`` was compared against. The ordering is
            # done on a separate blended value so that importance and
            # age can settle close calls without changing what a score
            # of 0.7 means.
            results.append(
                MemorySearchResult(
                    memory=memory,
                    score=score,
                )
            )
            rankings.append(
                score
                * self._rank_multiplier(
                    memory.importance, memory.created_at
                )
            )

        # Ordered by the blend, not by similarity — this is the whole
        # of the change. Sorting the pairs together keeps the ranking
        # and the results in step without touching ``score``.
        order = sorted(
            range(len(results)),
            key=lambda index: rankings[index],
            reverse=True,
        )

        return [results[index] for index in order[: query.limit]]

    def _rank_multiplier(
        self,
        importance: MemoryImportance,
        created_at: datetime,
    ) -> float:
        """How much importance and age move a relevant memory.

        Args:
            importance: The memory's stored importance.
            created_at: When it was written.

        Returns:
            A multiplier around 1.0, applied to the similarity score.
        """
        importance_multiplier = 1.0 + _IMPORTANCE_STEP * (
            importance.value - MemoryImportance.NORMAL.value
        )

        age_days = max(
            0.0,
            (datetime.now() - created_at).total_seconds() / 86400.0,
        )

        recency_multiplier = _RECENCY_FLOOR + _RECENCY_RANGE * (
            0.5 ** (age_days / self._config.recency_half_life_days)
        )

        return importance_multiplier * recency_multiplier

    def stats(self) -> dict:
        """How many memories there are, and what they cost on disk.

        Kept as a plain dict rather than a model because it exists to be
        printed. Nothing prunes on its own, so this is the only thing
        that will ever tell the user the store is growing.

        Returns:
            Counts and byte totals.
        """
        assert self._connection is not None

        self._lock.acquire()
        try:
            row = self._connection.execute(
                """
                SELECT
                    COUNT(*),
                    COALESCE(SUM(LENGTH(embedding)), 0),
                    COALESCE(SUM(LENGTH(CAST(content AS BLOB))), 0)
                FROM memories
                """
            ).fetchone()
        finally:
            self._lock.release()

        return {
            "memories": row[0],
            "embedding_bytes": row[1],
            "content_bytes": row[2],
            "total_bytes": row[1] + row[2],
        }

    def prune(self) -> int:
        """Removes old, unimportant memories. Returns how many went.

        Deliberately never called automatically. Deleting memories is
        not something that should happen behind the user's back, so the
        policy lives in configuration and the call is the caller's to
        make. With the default settings this removes memories below
        NORMAL importance that are older than 180 days — things EON
        stored incidentally, months ago, that nothing has needed since.

        Returns:
            The number of memories removed.
        """
        assert self._connection is not None

        cutoff = datetime.now() - timedelta(
            days=self._config.prune_after_days
        )

        self._lock.acquire()
        try:
            cursor = self._connection.execute(
                """
                DELETE FROM memories
                WHERE importance < ?
                  AND created_at < ?
                """,
                (
                    self._config.prune_below_importance,
                    cutoff.isoformat(),
                ),
            )

            self._connection.commit()
            removed = cursor.rowcount
        finally:
            self._lock.release()

        if removed:
            logger.info(
                "Pruned %d old, low-importance memories.", removed
            )

        return removed

    def get_learned_phrase(
        self,
        raw_phrase: str,
    ) -> tuple[str, str] | None:
        """
        Look up a previously learned phrase -> intent mapping.

        This is a plain dictionary lookup (normalized phrase -> stored
        intent_type/target), not any kind of speech-model
        personalization — EON doesn't retrain or fine-tune anything as
        it "learns" a user's phrasing, it just remembers a mapping it
        was told about (see ``set_learned_phrase``).

        Args:
            raw_phrase: The phrase to look up. Matched after the same
                normalization applied in ``set_learned_phrase``
                (stripped, lowercased) — this is an exact-match lookup,
                not fuzzy matching.

        Returns:
            A ``(intent_type, target)`` tuple if a mapping was found,
            otherwise ``None``.
        """
        assert self._connection is not None

        normalized = self._normalize_phrase(raw_phrase)
        if not normalized:
            return None

        self._lock.acquire()
        try:
            cursor = self._connection.execute(
                """
                SELECT intent_type, target
                FROM learned_phrases
                WHERE raw_phrase = ?
                """,
                (normalized,),
            )
            row = cursor.fetchone()
        finally:
            self._lock.release()

        if row is None:
            return None

        return (row["intent_type"], row["target"])

    def set_learned_phrase(
        self,
        raw_phrase: str,
        intent_type: str,
        target: str,
    ) -> None:
        """
        Persist a phrase -> intent mapping so it's recognized directly
        next time, bypassing rule-based classification.

        Args:
            raw_phrase: The phrase to remember. Normalized (stripped,
                lowercased) before storage so lookups are
                case-insensitive.
            intent_type: The ``IntentType`` value (or ``ActionType``
                value — the two overlap 1:1 for every type this table
                is used with) to route this phrase to.
            target: The target string to route this phrase to, e.g. an
                app name.
        """
        assert self._connection is not None

        normalized = self._normalize_phrase(raw_phrase)
        if not normalized:
            return

        self._lock.acquire()
        try:
            self._connection.execute(
                """
                INSERT INTO learned_phrases (
                    raw_phrase,
                    intent_type,
                    target,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(raw_phrase) DO UPDATE SET
                    intent_type = excluded.intent_type,
                    target = excluded.target,
                    created_at = excluded.created_at
                """,
                (
                    normalized,
                    intent_type,
                    target,
                    datetime.now().isoformat(),
                ),
            )
            self._connection.commit()
        finally:
            self._lock.release()

        logger.info(
            "Learned phrase mapping: %r -> (%s, %r)",
            normalized,
            intent_type,
            target,
        )

    @staticmethod
    def _normalize_phrase(raw_phrase: str) -> str:
        """
        Normalizes a phrase for consistent learned-phrase lookups.
        """
        return raw_phrase.strip().lower()

    def clear(self) -> None:
        raise NotImplementedError

    def health_check(self) -> bool:
        return self._connection is not None

    def exists(
        self,
        content: str,
        threshold: float,
    ) -> bool:
        results = self.search(
            MemoryQuery(
                query=content,
                limit=1,
            )
        )

        return (
            len(results) > 0
            and results[0].score >= threshold
        )
