from __future__ import annotations

from pathlib import Path

from .models import ValidationRequest, ValidationResult
from .strategies import ValidationStrategy
from ..execution import CommandRunner


class Validator:
    """
    Validates a coding project using the existing command-execution
    layer.

    Responsibilities:
    - detect an appropriate validation command
    - create a validation request
    - execute it through CommandRunner
    - translate the command result into ValidationResult

    This class does not directly use subprocess.
    """

    def __init__(
        self,
        runner: CommandRunner,
        strategy: ValidationStrategy | None = None,
    ) -> None:
        self._runner = runner
        self._strategy = strategy or ValidationStrategy()

    def validate(
        self,
        project_root: Path,
        *,
        timeout: float = 120.0,
    ) -> ValidationResult:
        """
        Detect and execute the best available validation strategy.

        Returns a structured ValidationResult.
        """

        project_root = project_root.resolve()

        if not project_root.exists():
            return ValidationResult(
                success=False,
                command=[],
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
            )

        if not project_root.is_dir():
            return ValidationResult(
                success=False,
                command=[],
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
            )

        command = self._strategy.detect(project_root)

        if command is None:
            return ValidationResult(
                success=False,
                command=[],
                exit_code=None,
                stdout="",
                stderr="No supported validation strategy was detected.",
                timed_out=False,
            )

        request = ValidationRequest(
            command=command,
            working_directory=project_root,
            timeout=timeout,
        )

        result = self._runner.run(
            request.command,
            cwd=request.working_directory,
            timeout=request.timeout,
        )

        return ValidationResult(
            success=result.success,
            command=list(result.argv),
            exit_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
        )
