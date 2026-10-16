from __future__ import annotations

from .models import PatchOperation


class PatchApplier:
    """
    Applies validated patch operations.
    """

    def apply(
        self,
        operations: list[PatchOperation],
    ) -> int:
        """
        Apply every patch operation.

        Returns:
            Number of modified files.
        """

        changed = 0

        for operation in operations:

            operation.file.write_text(
                operation.updated,
                encoding="utf-8",
            )

            changed += 1

        return changed
