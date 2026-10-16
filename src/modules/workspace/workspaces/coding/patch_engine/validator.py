from __future__ import annotations

from .models import PatchOperation


class PatchValidator:
    """
    Validates patch operations before they are applied.
    """

    def validate(
        self,
        operations: list[PatchOperation],
    ) -> list[str]:
        """
        Return a list of validation errors.

        Empty list means every patch is safe.
        """

        errors: list[str] = []

        for operation in operations:

            if not operation.file.exists():
                errors.append(
                    f"{operation.file} does not exist."
                )

            if operation.original == operation.updated:
                errors.append(
                    f"{operation.file} contains no changes."
                )

        return errors
