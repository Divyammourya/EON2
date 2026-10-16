"""
Git manager for the Coding Workspace.

Provides Git repository information for the currently opened project.

This class intentionally knows nothing about AI, editors, terminals,
or workspaces. It is responsible only for interacting with Git.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .models import GitFileStatus
from .project_manager import ProjectManager

from .models import (
    GitCommit,
    GitFileStatus,
)

class GitManager:
    """
    Provides Git operations for the current project.
    """

    def __init__(
        self,
        project_manager: ProjectManager,
    ) -> None:
        self._project_manager = project_manager

    def is_repository(self) -> bool:
        """
        Return True if the current project is a Git repository.
        """

        if not self._project_manager.has_project():
            return False

        return (
            self._run_git(
                "rev-parse",
                "--is-inside-work-tree",
            )
            == "true"
        )

    def current_branch(self) -> str | None:
        """
        Return the currently checked-out branch.
        """

        if not self.is_repository():
            return None

        return self._run_git(
            "branch",
            "--show-current",
        )

    def status(self) -> str:
        """
        Return the output of `git status --short`.
        """

        if not self.is_repository():
            return ""

        return self._run_git(
            "status",
            "--porcelain",
        )

    def _run_git(self, *args: str) -> str:
        """
        Execute a Git command inside the current project.
        """

        project = self._project_manager.project_root
        assert project is not None

        result = subprocess.run(
            ["git", *args],
            cwd=project,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return ""

        return result.stdout.strip()

    def changed_files(self) -> list[GitFileStatus]:
        """
        Return all changed files in the repository.
        """

        if not self.is_repository():
            return []

        output = self._run_git(
            "status",
            "--porcelain",
        )

        if not output:
            return []

        project = self._project_manager.project_root
        assert project is not None

        files: list[GitFileStatus] = []

        for line in output.splitlines():
            index = line[0]
            worktree = line[1]
            relative = line[3:]

            files.append(
                GitFileStatus(
                    path=project / relative,
                    index_status=index,
                    working_tree_status=worktree,
                )
            )

        return files

    def has_changes(self) -> bool:
        """
        Return True if the repository contains uncommitted changes.
        """

        return bool(self.changed_files())

    def log(
        self,
        limit: int = 20,
    ) -> list[GitCommit]:
        """
        Return recent commits.
        """

        if not self.is_repository():
            return []

        output = self._run_git(
            "log",
            f"-{limit}",
            "--pretty=format:%H|%h|%an|%ae|%at|%s",
        )

        if not output:
            return []

        commits: list[GitCommit] = []

        for line in output.splitlines():
            (
                commit_hash,
                short_hash,
                author,
                email,
                timestamp,
                subject,
            ) = line.split("|", 5)

            commits.append(
                GitCommit(
                    hash=commit_hash,
                    short_hash=short_hash,
                    author=author,
                    email=email,
                    timestamp=int(timestamp),
                    subject=subject,
                )
            )

        return commits
