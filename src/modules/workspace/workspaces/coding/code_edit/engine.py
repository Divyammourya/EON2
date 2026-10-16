from __future__ import annotations

from pathlib import Path

from .diff import DiffGenerator
from .editor import SourceEditor
from .locator import SymbolLocator
from .models import EditRequest, EditResult
from .parser import PythonParser

class CodeEditEngine:
    """
    High-level orchestrator for code editing.

    Coordinates parsing, locating symbols,
    editing source code and generating diffs.
    """

    def __init__(self) -> None:

        self.parser = PythonParser()
        self.locator = SymbolLocator()
        self.editor = SourceEditor()
        self.diff = DiffGenerator()

    def edit_symbol(
        self,
        request: EditRequest,
    ) -> EditResult:
        """
        Replace a class/function/method.
        """

        source = request.file.read_text(
            encoding="utf-8",
        )

        _ = self.parser.parse(source)

        node = self.locator.find(
            request.file,
            request.symbol,
        )

        if node is None:
            return EditResult(
                success=False,
                original=source,
                updated=source,
                message=f"Symbol '{request.symbol}' not found.",
            )

        original, updated = self.editor.replace_node(
            file=request.file,
            node=node,
            replacement=request.instruction,
        )

        return EditResult(
            success=True,
            original=original,
            updated=updated,
            message=self.diff.unified_diff(
                original,
                updated,
                filename=request.file.name,
            ),
        )
