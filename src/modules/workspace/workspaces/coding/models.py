from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


@dataclass(slots=True)
class GitFileStatus:
    """
    Represents the Git status of a single file.
    """

    path: Path
    index_status: str
    working_tree_status: str


@dataclass(slots=True)
class GitCommit:
    """
    Represents a Git commit.
    """

    hash: str
    short_hash: str
    author: str
    email: str
    timestamp: int
    subject: str


@dataclass(slots=True)
class IndexedFile:
    """
    Represents a single file discovered during repository indexing.

    Produced and owned by `RepositoryIndexer`. Plain data only — no
    behavior — matching the convention already used by every other
    model in this module.
    """

    path: Path
    relative_path: Path
    extension: str
    language: str | None
    size_bytes: int
    line_count: int


@dataclass(slots=True)
class RepositoryIndex:
    """
    Immutable snapshot of a project's file inventory at a point in time.

    Produced by `RepositoryIndexer.build_index()`. Future Phase 2
    components (SymbolIndexer, DependencyGraph, ContextBuilder) consume
    this rather than walking the filesystem themselves.
    """

    project_root: Path
    files: list[IndexedFile]
    generated_at: datetime

    def file_count(self) -> int:
        return len(self.files)

    def total_size_bytes(self) -> int:
        return sum(file.size_bytes for file in self.files)

    def total_line_count(self) -> int:
        return sum(file.line_count for file in self.files)

    def language_breakdown(self) -> dict[str, int]:
        """
        Return a count of indexed files per detected language.

        Files with no recognized language are grouped under "unknown".
        """

        counts: dict[str, int] = {}

        for file in self.files:
            key = file.language or "unknown"
            counts[key] = counts.get(key, 0) + 1

        return counts


class SymbolKind(str, Enum):
    """
    The kind of a code symbol.

    Kept intentionally small. New kinds (e.g. INTERFACE, ENUM) get added
    here as new SymbolExtractor implementations need them — this is the
    one shared vocabulary every extractor speaks, regardless of language.
    """

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"


@dataclass(slots=True)
class Symbol:
    """
    A single named code symbol discovered inside one file.

    Produced by a `SymbolExtractor` and collected by `SymbolIndexer`.
    Plain data only, same convention as every other model here.
    """

    name: str
    kind: SymbolKind
    file: Path          # path relative to the project root
    line: int
    language: str
