"""
Symbol indexer for the Coding Workspace.

Builds a per-file map of code symbols (functions, classes, methods) by
delegating to whichever `SymbolExtractor` supports each indexed file's
detected language. Consumes a `RepositoryIndexer` rather than the
filesystem directly — file discovery and ignore-rules are that class's
job, not this one's.

This class intentionally knows nothing about *how* a symbol is parsed
out of a file (that's each `SymbolExtractor`'s job) or how the project
was discovered (that's `RepositoryIndexer`'s job). Its one
responsibility is: given a repository index, produce and cache a
symbol map, and answer simple lookups against it.
"""

from __future__ import annotations

from pathlib import Path

from .models import Symbol
from .repository_indexer import RepositoryIndexer
from .symbol_extractor import PythonSymbolExtractor, SymbolExtractor


class SymbolIndexer:
    """
    Builds and caches a symbol map for the currently indexed project.
    """

    def __init__(
        self,
        repository_indexer: RepositoryIndexer,
        *,
        extractors: list[SymbolExtractor] | None = None,
    ) -> None:
        self._repository_indexer = repository_indexer

        # Defaults to Python only today. New languages are added by
        # passing more extractors here — SymbolIndexer itself never
        # needs to change.
        self._extractors: list[SymbolExtractor] = (
            extractors if extractors is not None else [PythonSymbolExtractor()]
        )

        # Instance-scoped cache, same pattern as RepositoryIndexer's
        # own `_index` cache. Keyed by each file's relative path.
        self._symbols: dict[Path, list[Symbol]] | None = None

    def build_index(self) -> dict[Path, list[Symbol]]:
        """
        Walk the current RepositoryIndex and extract symbols from every
        file whose language is supported by a registered extractor.

        Replaces any previously cached symbol map.
        """

        repository_index = self._repository_indexer.get_index()
        symbols: dict[Path, list[Symbol]] = {}

        for file in repository_index.files:
            extractor = self._find_extractor(file.language)

            if extractor is None:
                continue

            file_symbols = extractor.extract(file)

            if file_symbols:
                symbols[file.relative_path] = file_symbols

        self._symbols = symbols
        return symbols

    def get_index(self) -> dict[Path, list[Symbol]]:
        """
        Return the cached symbol map, building it if none exists yet.
        """

        if self._symbols is None:
            return self.build_index()

        return self._symbols

    def invalidate(self) -> None:
        """
        Discard the cached symbol map.

        Callers that invalidate the underlying RepositoryIndex (or that
        know its cache is stale) should invalidate this one too — the
        two caches are related but deliberately not auto-synchronized,
        since SymbolIndexer doesn't reach into RepositoryIndexer's
        internals to watch for that itself.
        """

        self._symbols = None

    def symbols_in_file(self, relative_path: Path) -> list[Symbol]:
        """
        Return the symbols found in a specific file, or an empty list
        if the file has none (or wasn't indexed).
        """

        return self.get_index().get(relative_path, [])

    def find_symbol(self, name: str) -> list[Symbol]:
        """
        Return every symbol across the project matching `name` exactly.

        Matches on the symbol's own name, so for methods this matches
        against "ClassName.method_name", not just "method_name" — bare
        method-name lookup is a reasonable follow-up but would require
        deciding how to disambiguate collisions across classes, which
        is out of scope for this first pass.
        """

        return [
            symbol
            for file_symbols in self.get_index().values()
            for symbol in file_symbols
            if symbol.name == name
        ]

    def _find_extractor(self, language: str | None) -> SymbolExtractor | None:
        for extractor in self._extractors:
            if extractor.supports(language):
                return extractor

        return None
