from __future__ import annotations

from .models import PatchResult


class Rollback:
    """
    Tracks applied patches so the most recently applied one can be
    undone.

    Keeps a simple in-memory stack of successfully applied
    PatchResults, owned by the PatchEngine instance that recorded
    them. This intentionally does not persist across process
    restarts — durable, multi-step undo history is future work
    (see project roadmap: "audit trail with undo capability").
    """

    def __init__(self) -> None:
        self._history: list[PatchResult] = []

    def record(self, result: PatchResult) -> None:
        """
        Record a successfully applied patch so it can later be rolled
        back. Failed patches (nothing written to disk) are ignored.
        """

        if result.success and result.operations:
            self._history.append(result)

    def rollback_last(self) -> PatchResult | None:
        """
        Restore every file touched by the most recently applied patch
        to its pre-patch content, then forget that patch.

        Returns None if there is nothing to roll back.
        """

        if not self._history:
            return None

        result = self._history.pop()
        changed = 0

        for operation in result.operations:
            operation.file.write_text(
                operation.original,
                encoding="utf-8",
            )
            changed += 1

        return PatchResult(
            success=True,
            changed_files=changed,
            operations=result.operations,
            message=f"Rolled back {changed} file(s).",
        )

    def has_history(self) -> bool:
        """
        Whether there is at least one applied patch available to roll
        back.
        """

        return bool(self._history)
