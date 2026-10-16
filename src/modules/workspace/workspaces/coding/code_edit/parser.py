from __future__ import annotations

import ast

from dataclasses import dataclass


@dataclass(slots=True)
class ParsedPython:
    """
    Parsed representation of a Python source file.
    """

    source: str
    tree: ast.Module


class PythonParser:
    """
    Parses Python source code.
    """

    def parse(
        self,
        source: str,
    ) -> ParsedPython:

        return ParsedPython(
            source=source,
            tree=ast.parse(source),
        )
