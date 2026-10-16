from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CommandRequest:
    """
    A command to execute inside the currently opened coding project.

    `argv` is deliberately represented as a sequence rather than a shell
    command string. This keeps shell=True out of the execution path and
    avoids shell quoting/injection problems.
    """

    argv: tuple[str, ...]
    cwd: Path
    timeout: float = 60.0
    env: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class CommandResult:
    """
    Result of one process execution.
    """

    success: bool
    argv: tuple[str, ...]
    cwd: Path
    return_code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_seconds: float = 0.0
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
