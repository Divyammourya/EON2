"""
Repository indexer for the Coding Workspace.

Responsible for walking the currently opened project and building a
structural inventory of its files: what exists, where, how large each
file is, and (heuristically) what language it's written in.

This is deliberately "dumb" inventory-building, not understanding. It
knows nothing about symbols, imports, dependency graphs, or semantic
meaning — that belongs to the SymbolIndexer / DependencyGraph /
ContextBuilder that will be layered on top of the file list this class
produces in later Phase 2 steps. Every one of those future components
will consume a RepositoryIndex rather than each re-walking the
filesystem with their own ignore rules, so this class exists to fix
file-discovery policy in exactly one place.

This class intentionally knows nothing about Git, editors, AI, or
search ranking. It is responsible only for producing and caching a
`RepositoryIndex`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .exceptions import NoProjectOpenError
from .models import IndexedFile, RepositoryIndex
from .project_manager import ProjectManager


# Directories that are never useful to index: VCS internals, dependency
# caches, build artifacts, and virtual environments. This is fixed
# policy, not mutable state — it lives at module scope for the same
# reason a constant does, not as a workaround for global state.
DEFAULT_IGNORED_DIRECTORIES: frozenset[str] = frozenset({
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "venv",
    ".venv",
    "env",
    "dist",
    "build",
    ".next",
    ".turbo",
    "target",
    ".idea",
    ".vscode",
})

# Heuristic extension -> language map. Intentionally small and
# unopinionated. A future SymbolIndexer can extend or replace this
# mapping without needing to change indexing policy itself.
_EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".html": "html",
    ".css": "css",
}


class RepositoryIndexer:
    """
    Builds and caches a structural index of the currently opened project.
    """

    def __init__(
        self,
        project_manager: ProjectManager,
        *,
        ignored_directories: frozenset[str] = DEFAULT_IGNORED_DIRECTORIES,
    ) -> None:
        self._project_manager = project_manager
        self._ignored_directories = ignored_directories

        # Cached result of the last build_index() call. This is
        # instance-scoped state owned by this indexer (one per
        # CodingWorkspace instance) — not global state. It only ever
        # reflects the project this indexer's ProjectManager currently
        # has open.
        self._index: RepositoryIndex | None = None

    @property
    def project_root(self) -> Path:
        root = self._project_manager.project_root

        if root is None:
            raise NoProjectOpenError(
                "No project is currently open."
            )

        return root

    def build_index(self) -> RepositoryIndex:
        """
        Walk the project and build a fresh RepositoryIndex.

        Replaces any previously cached index.
        """

        root = self.project_root
        files: list[IndexedFile] = []

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if self._is_ignored(path, root):
                continue

            files.append(self._index_file(path, root))

        self._index = RepositoryIndex(
            project_root=root,
            files=files,
            generated_at=datetime.now(timezone.utc),
        )

        return self._index

    def get_index(self) -> RepositoryIndex:
        """
        Return the cached index, building it if none exists yet.
        """

        if self._index is None:
            return self.build_index()

        return self._index

    def invalidate(self) -> None:
        """
        Discard the cached index.

        The next call to get_index() will rebuild from disk. This
        indexer does not watch the filesystem itself — whichever
        component mutates project files (e.g. a future patch-applying
        CodingAgent) is responsible for calling this afterwards.
        """

        self._index = None

    def _is_ignored(self, path: Path, root: Path) -> bool:
        relative_parts = path.relative_to(root).parts

        # Every path segment except the filename itself is a directory
        # component; ignore the file if any of them is a known
        # ignored directory name.
        return any(
            part in self._ignored_directories
            for part in relative_parts[:-1]
        )

    def _index_file(self, path: Path, root: Path) -> IndexedFile:
        extension = path.suffix
        size_bytes = path.stat().st_size

        return IndexedFile(
            path=path,
            relative_path=path.relative_to(root),
            extension=extension,
            language=_EXTENSION_LANGUAGE_MAP.get(extension),
            size_bytes=size_bytes,
            line_count=self._count_lines(path),
        )

    @staticmethod
    def _count_lines(path: Path) -> int:
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                return sum(1 for _ in handle)
        except OSError:
            return 0
