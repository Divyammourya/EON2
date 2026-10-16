"""
Symbol extractors for the Coding Workspace's Symbol Index layer.

A `SymbolExtractor` knows how to pull named symbols (functions, classes,
methods) out of a single file written in one specific language. This is
the seam that lets `SymbolIndexer` stay language-agnostic: it never
parses source itself, it only asks "which extractor supports this
file's language?" and delegates.

Adding support for a new language means writing a new SymbolExtractor
and registering it with SymbolIndexer — no existing code changes.
"""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod

from .models import IndexedFile, Symbol, SymbolKind


class SymbolExtractor(ABC):
    """
    Extracts symbols from a single file written in a language this
    extractor understands.
    """

    @abstractmethod
    def supports(self, language: str | None) -> bool:
        """
        Return True if this extractor can handle the given language.
        """

        raise NotImplementedError

    @abstractmethod
    def extract(self, file: IndexedFile) -> list[Symbol]:
        """
        Return the symbols found in `file`.

        Must not raise on malformed input — a file that fails to parse
        (syntax error, encoding issue, etc.) simply yields no symbols,
        since one broken file should never take down indexing for the
        rest of the project.
        """

        raise NotImplementedError


class PythonSymbolExtractor(SymbolExtractor):
    """
    Extracts top-level functions/classes and class methods from Python
    source using the standard library `ast` module.

    Deliberately exact rather than heuristic: `ast` gives real syntax
    trees, so what it reports is guaranteed structurally correct for
    any file that parses. Files that don't parse are skipped, not
    guessed at.
    """

    def supports(self, language: str | None) -> bool:
        return language == "python"

    def extract(self, file: IndexedFile) -> list[Symbol]:
        try:
            source = file.path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=str(file.path))
        except (SyntaxError, OSError, UnicodeDecodeError, ValueError):
            return []

        symbols: list[Symbol] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(
                    Symbol(
                        name=node.name,
                        kind=SymbolKind.FUNCTION,
                        file=file.relative_path,
                        line=node.lineno,
                        language="python",
                    )
                )
            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    Symbol(
                        name=node.name,
                        kind=SymbolKind.CLASS,
                        file=file.relative_path,
                        line=node.lineno,
                        language="python",
                    )
                )
                symbols.extend(self._extract_methods(node, file))

        return symbols

    @staticmethod
    def _extract_methods(
        class_node: ast.ClassDef, file: IndexedFile
    ) -> list[Symbol]:
        methods: list[Symbol] = []

        for child in ast.iter_child_nodes(class_node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(
                    Symbol(
                        name=f"{class_node.name}.{child.name}",
                        kind=SymbolKind.METHOD,
                        file=file.relative_path,
                        line=child.lineno,
                        language="python",
                    )
                )

        return methods
