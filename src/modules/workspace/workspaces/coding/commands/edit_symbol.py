from __future__ import annotations

from ..code_edit.models import EditRequest
from .base import CodingCommand


class EditSymbolCommand(CodingCommand):
    """
    Replaces a class/function/method inside a project file with a
    literal replacement string.

    Runs the edit through CodeEditEngine (locate the symbol, compute
    the updated source, generate a diff) and then PatchEngine
    (validate, apply, record for rollback). Nothing is written to
    disk unless both stages succeed.
    """

    def __init__(
        self,
        file_manager,
        edit_engine,
        patch_engine,
        patch_builder,
        file: str,
        symbol: str,
        replacement: str,
    ):
        self.file_manager = file_manager
        self.edit_engine = edit_engine
        self.patch_engine = patch_engine
        self.patch_builder = patch_builder
        self.file = file
        self.symbol = symbol
        self.replacement = replacement

    def execute(self):

        absolute = self.file_manager.resolve_path(
            self.file,
        )

        edit_result = self.edit_engine.edit_symbol(
            EditRequest(
                file=absolute,
                symbol=self.symbol,
                instruction=self.replacement,
            ),
        )

        if not edit_result.success:
            return {
                "success": False,
                "file": str(absolute),
                "symbol": self.symbol,
                "error": edit_result.message,
            }

        operation = self.patch_builder.build(
            file=absolute,
            original=edit_result.original,
            updated=edit_result.updated,
        )

        patch_result = self.patch_engine.apply(
            [operation],
        )

        return {
            "success": patch_result.success,
            "file": str(absolute),
            "symbol": self.symbol,
            "diff": edit_result.message,
            "changed_files": patch_result.changed_files,
            "message": patch_result.message,
        }
