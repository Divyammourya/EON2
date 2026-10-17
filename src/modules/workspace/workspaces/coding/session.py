"""The folder EON does its coding in.

Every project EON builds gets its own folder inside a single workspace
root, so a coding session can never reach outside it. The root is the
boundary and the project folder is the working directory:

    ~/Desktop/EON_workspace/          <- the root (the boundary)
        calculator/                   <- one project
            src/main.py
        todo-app/                     <- another project
            index.html

Design notes:
    - The root is deliberately *not* your home directory or your
      Desktop. EON writes files here on its own, and a coding agent
      pointed at a whole home directory is one bad instruction away
      from a bad afternoon. One folder, named for what it is.
    - A project name is sanitised down to a single safe folder name.
      This matters more than it looks: the name comes from what you
      typed, so "coding ../../.." would otherwise be a way to create a
      project outside the root. Anything that isn't a plain name is
      rejected rather than quietly rewritten into something
      surprising.
    - Reads and writes are confined by resolving the path and checking
      it is still under the project folder — the same check the coding
      workspace's own FileManager makes. Two independent checks for a
      boundary this important is not redundancy, it's the point.

Requires: Python 3.12+ (no extra packages)
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("CodingSession")

# Where projects go when nothing is configured. Matches the folder
# layout a Windows user expects ("Desktop\EON_workspace").
DEFAULT_WORKSPACE_ROOT = "~/Desktop/EON_workspace"

# A project name has to survive being a folder name on Windows, macOS
# and Linux. Letters, digits, spaces, dash, underscore and dot; no
# path separators, no leading dot (a hidden folder), no ".." anywhere.
_SAFE_PROJECT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-]{0,63}$")

# Enough files to show in a window without walking forever. A coding
# session's own project is small; a limit stops a mistaken root (say,
# a whole home directory) from hanging the UI.
MAX_LISTED_FILES = 2000


class CodingSessionError(Exception):
    """Raised when a coding session cannot be started or used."""


@dataclass(slots=True)
class ProjectFile:
    """One file in the project, as the window needs to show it."""

    path: Path
    relative: str
    size_bytes: int


def sanitise_project_name(name: str) -> str:
    """Turns what the user typed into a safe single folder name.

    Args:
        name: The raw project name.

    Returns:
        The cleaned name.

    Raises:
        CodingSessionError: If nothing usable is left, or the name
            isn't a plain name — a name containing path separators or
            ``..`` is rejected outright rather than silently rewritten,
            because a rewritten name is not the project you asked for.
    """
    # Only whitespace is normalised. Dots are deliberately *not*
    # stripped: ".hidden" would silently become "hidden", which is a
    # different folder from the one asked for, and a name that has to be
    # changed to be usable is better refused than quietly rewritten.
    cleaned = " ".join(name.split()).strip()

    if not cleaned:
        raise CodingSessionError(
            "I need a name for the project — try 'coding calculator'."
        )

    if not _SAFE_PROJECT_NAME.match(cleaned):
        raise CodingSessionError(
            f"'{name}' isn't a usable project name. Letters, digits, "
            "spaces, dashes and underscores only."
        )

    return cleaned


class CodingSession:
    """One project, inside the workspace root.

    Attributes:
        root: The workspace root — the boundary.
        project_root: The folder this session works in.
        name: The project's name.
    """

    def __init__(
        self,
        *,
        root: str | Path = DEFAULT_WORKSPACE_ROOT,
        name: str,
    ) -> None:
        self.root = Path(root).expanduser().resolve()

        self.name = sanitise_project_name(name)

        self.project_root = self.root / self.name

        self._ensure_project_folder()

    @property
    def project_root_display(self) -> str:
        """The project folder as a string, for showing to the user."""
        return str(self.project_root)

    def _ensure_project_folder(self) -> None:
        """Creates the root and the project folder if they don't exist."""
        try:
            self.project_root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise CodingSessionError(
                f"I couldn't create {self.project_root}: {error}"
            ) from error

        logger.info(
            "Coding session '%s' in %s.",
            self.name,
            self.project_root,
        )

    def resolve(self, path: str) -> Path:
        """Resolves a project-relative path, refusing to leave the project.

        Args:
            path: A path relative to the project folder.

        Returns:
            The absolute path.

        Raises:
            CodingSessionError: If the path escapes the project folder.
        """
        # "~" is deliberately not expanded. Left alone it resolves to a
        # folder literally called "~" inside the project, which is odd
        # but harmless; expanded, it would point at your home directory,
        # which is the one place EON must never write. Refusing is both
        # clearer and safer than either.
        if path.startswith("~"):
            raise CodingSessionError(
                "'~' means your home folder, and I only work inside "
                f"{self.project_root}. Give me a path inside the project."
            )

        candidate = Path(path)

        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.project_root / candidate).resolve()

        if resolved != self.project_root and self.project_root not in resolved.parents:
            raise CodingSessionError(
                f"'{path}' is outside the project — I only work inside "
                f"{self.project_root}."
            )

        return resolved

    def write_file(self, path: str, content: str = "") -> ProjectFile:
        """Writes a file inside the project.

        Args:
            path: Project-relative path.
            content: The text to write.

        Returns:
            The written file.

        Raises:
            CodingSessionError: If the path escapes the project, or the
                write fails.
        """
        target = self.resolve(path)

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as error:
            raise CodingSessionError(
                f"I couldn't write {path}: {error}"
            ) from error

        return ProjectFile(
            path=target,
            relative=self.relative_to_project(target),
            size_bytes=target.stat().st_size,
        )

    def read_file(self, path: str) -> str:
        """Reads a file inside the project.

        Args:
            path: Project-relative path.

        Returns:
            The file's text.

        Raises:
            CodingSessionError: If the path escapes the project or the
                file can't be read.
        """
        target = self.resolve(path)

        try:
            return target.read_text(encoding="utf-8")
        except OSError as error:
            raise CodingSessionError(
                f"I couldn't read {path}: {error}"
            ) from error

    def relative_to_project(self, path: Path) -> str:
        """A path as the user should see it — relative to the project."""
        try:
            return str(path.relative_to(self.project_root)).replace("\\", "/")
        except ValueError:
            return str(path)

    def list_files(self, *, limit: int = MAX_LISTED_FILES) -> list[ProjectFile]:
        """Every file in the project, sorted, for the window's tree.

        Args:
            limit: Stop after this many files.

        Returns:
            The files found.
        """
        found: list[ProjectFile] = []

        try:
            candidates = sorted(self.project_root.rglob("*"))
        except OSError as error:
            logger.warning("Could not list %s: %s", self.project_root, error)
            return []

        for path in candidates:
            try:
                if not path.is_file():
                    continue
                size = path.stat().st_size
            except OSError:
                continue

            found.append(
                ProjectFile(
                    path=path,
                    relative=self.relative_to_project(path),
                    size_bytes=size,
                )
            )

            if len(found) >= limit:
                break

        return found

    def file_count(self) -> int:
        """How many files the project holds."""
        return len(self.list_files())

    def delete(self) -> None:
        """Removes the project folder.

        Only ever called with the user's explicit say-so — see
        CodingMode.
        """
        if self.project_root == self.root:
            raise CodingSessionError(
                "Refusing to delete the workspace root itself."
            )

        shutil.rmtree(self.project_root, ignore_errors=True)

        logger.info("Deleted project %s.", self.project_root)


def list_projects(root: str | Path = DEFAULT_WORKSPACE_ROOT) -> list[str]:
    """The projects that already exist in the workspace root.

    Args:
        root: The workspace root.

    Returns:
        Project names, sorted. Empty if the root doesn't exist yet.
    """
    root_path = Path(root).expanduser()

    if not root_path.is_dir():
        return []

    try:
        return sorted(
            entry.name
            for entry in root_path.iterdir()
            if entry.is_dir() and not entry.name.startswith(".")
        )
    except OSError:
        return []
