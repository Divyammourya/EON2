"""Answers the coding window's sidebar questions.

The window needs three things it cannot work out for itself: what in
the project contains some text, what symbols a file defines, and what
git says about the branch. EON already knew all three — but only
through console commands, so none of it was ever on screen.

This module is the adapter between the two. It exists so that
``window.py`` can stay ignorant of the workspace: the window asks a
question and gets plain tuples back, and never imports a
``SearchManager``.

Every method is written to return *nothing* rather than raise. A
sidebar section that cannot answer is a sidebar section that is empty,
not a window that fails to open — the same rule the rest of the coding
feature follows.

Requires: Python 3.12+ (no extra packages)
"""

from __future__ import annotations

from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("CodingWindowQueries")

# Don't read anything larger than this looking for a match. Searching a
# 50 MB file for a word is not what the search box is for.
MAX_SEARCH_BYTES = 2_000_000


class WindowQueries:
    """The window's questions, answered from the coding workspace.

    Attributes:
        _workspace: The coding workspace whose managers are consulted.
    """

    def __init__(self, workspace) -> None:
        """Builds the adapter.

        Args:
            workspace: The coding workspace. Anything exposing
                ``search``, ``symbol_indexer``, ``git`` and
                ``project_manager`` will do, which is what lets the
                tests drive a stub.
        """
        self._workspace = workspace

    # --- search -----------------------------------------------------------

    def search(self, text: str) -> list[tuple[str, int]]:
        """Files containing ``text``, with the line of the first match.

        Args:
            text: What to look for. Matched case-sensitively, the same
                way EON's own ``search project`` command matches.

        Returns:
            ``(relative path, line number)`` pairs, sorted by path.
            The line number is 1-based; 0 means "found in the file, but
            not on a line I could point at" — a binary-ish file, say.
        """
        text = text.strip()

        if not text:
            return []

        manager = getattr(self._workspace, "search", None)

        if manager is None:
            return []

        try:
            matches = manager.search_text(text)
        except Exception as error:  # pragma: no cover - backend safety net
            logger.warning("Search failed: %s", error)
            return []

        results: list[tuple[str, int]] = []

        for path in matches:
            relative = self._relative(path)

            if relative is None:
                continue

            results.append((relative, self._first_line(path, text)))

        return sorted(results)

    def _first_line(self, path: Path, text: str) -> int:
        """The 1-based line number of the first match, or 0."""
        try:
            if path.stat().st_size > MAX_SEARCH_BYTES:
                return 0

            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return 0

        for number, line in enumerate(content.splitlines(), start=1):
            if text in line:
                return number

        return 0

    # --- outline ----------------------------------------------------------

    def outline(self, relative: str) -> list[tuple[str, str, int]]:
        """The symbols defined in one file.

        Args:
            relative: The file's path relative to the project root.

        Returns:
            ``(name, kind, line)`` triples in the order the file
            defines them.
        """
        indexer = getattr(self._workspace, "symbol_indexer", None)

        if indexer is None:
            return []

        try:
            symbols = indexer.symbols_in_file(Path(relative))
        except Exception as error:  # pragma: no cover - backend safety net
            logger.warning("Could not read symbols for %s: %s", relative, error)
            return []

        found: list[tuple[str, str, int]] = []

        for symbol in symbols:
            kind = getattr(symbol, "kind", None)
            kind_name = getattr(kind, "value", None) or str(kind or "symbol")

            found.append(
                (
                    str(getattr(symbol, "name", "?")),
                    str(kind_name),
                    int(getattr(symbol, "line", 0) or 0),
                )
            )

        return found

    # --- git --------------------------------------------------------------

    def git(self) -> tuple[str | None, list[tuple[str, str]]]:
        """The current branch and the files that changed on it.

        Returns:
            ``(branch, changed)`` where ``branch`` is ``None`` outside
            a repository, and ``changed`` is ``(relative path, status)``
            pairs such as ``("src/main.py", "M")``.
        """
        manager = getattr(self._workspace, "git", None)

        if manager is None:
            return None, []

        try:
            if not manager.is_repository():
                return None, []

            branch = manager.current_branch()
            changed = manager.changed_files()
        except Exception as error:  # pragma: no cover - backend safety net
            logger.warning("Could not read git status: %s", error)
            return None, []

        files: list[tuple[str, str]] = []

        for entry in changed:
            relative = self._relative(getattr(entry, "path", None))

            if relative is None:
                continue

            files.append((relative, _status_letter(entry)))

        return branch, sorted(files)

    # --- helpers ----------------------------------------------------------

    def _relative(self, path) -> str | None:
        """A path as the project-relative string the window uses.

        Accepts absolute paths (which the search manager returns) and
        already-relative ones (which git returns), so callers don't
        have to care which they got.
        """
        if path is None:
            return None

        try:
            path = Path(path)
        except TypeError:
            return None

        root = getattr(
            getattr(self._workspace, "project_manager", None),
            "project_root",
            None,
        )

        if root is not None:
            try:
                return str(path.relative_to(Path(root))).replace("\\", "/")
            except ValueError:
                # Not under the project root — fall through and report
                # it as it came, rather than dropping it silently.
                pass

        return str(path).replace("\\", "/")


def _status_letter(entry) -> str:
    """A one-letter summary of a git file status.

    Git reports two columns — the index and the working tree — and the
    window has room for one. Working-tree changes are what you can see
    in the editor, so those win.
    """
    working = str(getattr(entry, "working_tree_status", "") or "").strip()
    index = str(getattr(entry, "index_status", "") or "").strip()

    letter = working or index

    if not letter:
        return "?"

    if letter in {"??", "?"}:
        return "?"

    return letter[0]
