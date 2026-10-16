from __future__ import annotations

import ast

from .base import CodingCommand
from .edit_symbol import EditSymbolCommand


class AIEditSymbolCommand(CodingCommand):
    """
    Edits a symbol from a natural-language instruction instead of a
    literal replacement string.

    Locates the symbol, extracts its current source, gathers
    cross-file context (imports, sibling symbols, callers) via the
    `SymbolContextBuilder`, asks the `AICodeEditor` to generate
    replacement source for it, then hands that replacement to
    `EditSymbolCommand` — so an AI-generated edit goes through
    exactly the same format/validate/patch/rollback path as a
    manually supplied one.
    """

    def __init__(
        self,
        file_manager,
        edit_engine,
        patch_engine,
        patch_builder,
        ai_editor,
        context_builder,
        file: str,
        symbol: str,
        instruction: str,
    ):
        self.file_manager = file_manager
        self.edit_engine = edit_engine
        self.patch_engine = patch_engine
        self.patch_builder = patch_builder
        self.ai_editor = ai_editor
        self.context_builder = context_builder
        self.file = file
        self.symbol = symbol
        self.instruction = instruction

    def execute(self):

        absolute = self.file_manager.resolve_path(
            self.file,
        )

        source = absolute.read_text(
            encoding="utf-8",
        )

        node = self.edit_engine.locator.find(
            absolute,
            self.symbol,
        )

        if node is None:
            return {
                "success": False,
                "file": str(absolute),
                "symbol": self.symbol,
                "error": f"Symbol '{self.symbol}' not found.",
            }

        current_source = ast.get_source_segment(
            source,
            node,
        )

        if current_source is None:
            current_source = ""

        context = self.context_builder.build(
            file=absolute,
            symbol=self.symbol,
        )

        replacement = self.ai_editor.generate_replacement(
            symbol=self.symbol,
            current_source=current_source,
            instruction=self.instruction,
            context=context.render(),
        )

        delegate = EditSymbolCommand(
            self.file_manager,
            self.edit_engine,
            self.patch_engine,
            self.patch_builder,
            self.file,
            self.symbol,
            replacement,
        )

        result = delegate.execute()
        result["instruction"] = self.instruction

        return result
