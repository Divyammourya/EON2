from __future__ import annotations

import ast

from pathlib import Path


class SourceEditor:
    """
    Performs line-based source code edits.

    This class is intentionally independent from AI,
    Git, and workspaces.
    """

    def replace_node(
        self,
        *,
        file: Path,
        node: ast.AST,
        replacement: str,
    ) -> tuple[str, str]:
        """
        Compute the result of replacing an AST node's source lines
        with `replacement`, without writing anything to disk.

        Deliberately read-only (unlike `replace_lines`): callers such
        as `CodeEditEngine.edit_symbol` need the updated source so it
        can be validated and routed through `PatchEngine` first —
        nothing should land on disk until that pipeline decides the
        edit is safe to apply.

        Returns:
            (original_source, updated_source)
        """

        original = file.read_text(
            encoding="utf-8",
        )

        lines = original.splitlines()

        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)

        updated = (
            lines[: start_line - 1]
            + replacement.splitlines()
            + lines[end_line:]
        )

        updated_source = "\n".join(updated)

        return (
            original,
            updated_source,
        )

    def replace_lines(
        self,
        file: Path,
        start_line: int,
        end_line: int,
        replacement: str,
    ) -> tuple[str, str]:
        """
        Replace a range of lines inside a file.

        Returns:
            (original_source, updated_source)
        """

        original = file.read_text(
            encoding="utf-8",
        )

        lines = original.splitlines()

        updated = (
            lines[: start_line - 1]
            + replacement.splitlines()
            + lines[end_line:]
        )

        updated_source = "\n".join(updated)

        file.write_text(
            updated_source,
            encoding="utf-8",
        )

        return (
            original,
            updated_source,
        )
