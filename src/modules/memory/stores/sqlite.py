"""
SQLite Memory Store.

SQLite implementation of the MemoryStore interface.
"""

from __future__ import annotations

import json
import math
import threading

import sqlite3
from pathlib import Path
from datetime import datetime
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
                    json.dumps(memory.embedding)
                    if memory.embedding is not None
                    else None,
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

        for row in rows:

            if row["embedding"] is None:
                continue

            embedding = json.loads(row["embedding"])

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

            if score > query.min_score:
                results.append(
                    MemorySearchResult(
                        memory=memory,
                        score=score,
                    )
                )

        results.sort(
            key=lambda r: r.score,
            reverse=True,
        )

        return results[: query.limit]

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
