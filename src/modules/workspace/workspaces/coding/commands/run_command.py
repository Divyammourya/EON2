from __future__ import annotations

from ..execution import CommandRunner


class RunCommandCommand:
    """
    Command-layer adapter for terminal execution.

    The command itself does not decide what is safe or how a process
    should be launched; CommandRunner owns that behavior.
    """

    def __init__(
        self,
        runner: CommandRunner,
        command: str,
        *,
        timeout: float | None = None,
    ) -> None:
        self._runner = runner
        self._command = command
        self._timeout = timeout

    def execute(self) -> dict:
        result = self._runner.run(
            self._command,
            timeout=self._timeout,
        )

        return {
            "success": result.success,
            "command": list(result.argv),
            "cwd": str(result.cwd),
            "return_code": result.return_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
            "duration_seconds": result.duration_seconds,
            "error": result.error,
        }
