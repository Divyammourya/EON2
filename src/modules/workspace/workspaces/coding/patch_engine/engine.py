from __future__ import annotations

from .apply import PatchApplier
from .models import PatchOperation, PatchResult
from .rollback import Rollback
from .validator import PatchValidator


class PatchEngine:
    """
    Coordinates patch validation and application.

    Every edit made by EON should eventually flow through this
    engine before touching the filesystem.
    """

    def __init__(self) -> None:
        self.validator = PatchValidator()
        self.applier = PatchApplier()
        self.rollback = Rollback()

    def apply(
        self,
        operations: list[PatchOperation],
    ) -> PatchResult:
        """
        Validate and apply patch operations.
        """

        errors = self.validator.validate(
            operations,
        )

        if errors:
            return PatchResult(
                success=False,
                changed_files=0,
                operations=[],
                message="; ".join(errors),
            )

        changed = self.applier.apply(
            operations,
        )

        result = PatchResult(
            success=True,
            changed_files=changed,
            operations=operations,
            message=f"Applied {changed} patch(es).",
        )

        self.rollback.record(result)

        return result
