from __future__ import annotations

from pathlib import Path

from .models import PatchOperation


class PatchBuilder:
    """
    Builds PatchOperation objects for the PatchEngine.

    Kept separate from CodeEditEngine and PatchEngine: this class's
    only job is packaging an (original, updated) source pair for a
    file into the PatchOperation the PatchEngine understands. It
    performs no validation, no diffing, and no I/O of its own.
    """

    def build(
        self,
        *,
        file: Path,
        original: str,
        updated: str,
    ) -> PatchOperation:
        """
        Build a single PatchOperation from an edit's before/after
        source.
        """

        return PatchOperation(
            file=file,
            original=original,
            updated=updated,
        )

    def build_many(
        self,
        edits: list[tuple[Path, str, str]],
    ) -> list[PatchOperation]:
        """
        Build several PatchOperations at once.

        Intended for multi-file edits (e.g. renaming a symbol and
        updating every caller), where one logical change touches more
        than one file and should be validated/applied/rolled back as
        a single patch.
        """

        return [
            self.build(
                file=file,
                original=original,
                updated=updated,
            )
            for file, original, updated in edits
        ]
