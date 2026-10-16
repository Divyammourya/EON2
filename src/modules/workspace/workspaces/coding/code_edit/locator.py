from __future__ import annotations

import ast

from pathlib import Path


class SymbolLocator:
    """
    Locates classes, functions and methods inside Python files.
    """

    def find(
        self,
        file: Path,
        symbol: str,
    ) -> ast.AST | None:
        """
        Return the AST node for the requested symbol.
        """

        source = file.read_text(
            encoding="utf-8",
        )

        tree = ast.parse(source)

        for node in ast.walk(tree):

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):

                if node.name == symbol:
                    return node

        return None

    def list_symbols(
        self,
        file: Path,
    ) -> list[str]:
        """
        Return every class/function defined in the file.
        """

        source = file.read_text(
            encoding="utf-8",
        )

        tree = ast.parse(source)

        symbols = []

        for node in ast.walk(tree):

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):
                symbols.append(node.name)

        return sorted(symbols)
