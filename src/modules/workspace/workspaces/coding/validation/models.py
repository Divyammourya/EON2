from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ValidationRequest:
    """
    Describes a validation command that should be executed
    against the current project.
    """

    command: list[str]
    working_directory: Path
    timeout: float = 120.0


@dataclass(slots=True)
class ValidationResult:
    """
    Result produced by a validation run.
    """

    success: bool
    command: list[str]
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def output(self) -> str:
        """
        Combined validation output.
        """

        parts: list[str] = []

        if self.stdout:
            parts.append(self.stdout)

        if self.stderr:
            parts.append(self.stderr)

        return "\n".join(parts)
