from __future__ import annotations

import difflib


class DiffGenerator:
    """
    Generates unified diffs between two versions of source code.
    """

    def unified_diff(
        self,
        original: str,
        updated: str,
        *,
        filename: str = "file.py",
    ) -> str:
        """
        Return a Git-style unified diff.
        """

        diff = difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=filename,
            tofile=filename,
            lineterm="",
        )

        return "\n".join(diff)

    def has_changes(
        self,
        original: str,
        updated: str,
    ) -> bool:
        """
        Return True if the two versions differ.
        """

        return original != updated

    def changed_line_count(
        self,
        original: str,
        updated: str,
    ) -> int:
        """
        Return the number of changed lines.
        """

        diff = difflib.ndiff(
            original.splitlines(),
            updated.splitlines(),
        )

        return sum(
            1
            for line in diff
            if line.startswith("+ ")
            or line.startswith("- ")
        )
