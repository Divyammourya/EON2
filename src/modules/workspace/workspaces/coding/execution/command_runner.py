from __future__ import annotations

import os
import shlex
import subprocess
import time
from pathlib import Path

from .models import CommandRequest, CommandResult


class CommandRunner:
    """
    Runs developer commands inside a coding project.

    Design constraints:
    - never uses shell=True
    - defaults to the current project root as cwd
    - enforces a timeout
    - captures stdout/stderr
    - limits captured output
    - rejects obviously destructive command forms

    This is a process runner, not a security sandbox. A future production
    version should execute untrusted commands in an OS/container sandbox.
    """

    DEFAULT_TIMEOUT = 60.0
    MAX_OUTPUT_CHARS = 100_000

    # Deliberately conservative. These are not intended to be a complete
    # security policy; they only prevent common accidental destructive
    # commands from being issued through the coding tool.
    _BLOCKED_EXECUTABLES = frozenset({
        "format",
        "diskpart",
        "shutdown",
        "reboot",
        "poweroff",
        "mkfs",
    })

    def __init__(
        self,
        *,
        default_cwd: Path | None = None,
        default_timeout: float = DEFAULT_TIMEOUT,
        max_output_chars: int = MAX_OUTPUT_CHARS,
    ) -> None:
        self._default_cwd = (
            default_cwd.resolve()
            if default_cwd is not None
            else None
        )
        self._default_timeout = default_timeout
        self._max_output_chars = max_output_chars

    def run(
        self,
        command: str | list[str] | tuple[str, ...],
        *,
        cwd: Path | None = None,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """
        Execute a command without invoking a shell.

        A string is tokenized with shlex only; shell operators such as
        `|`, `&&`, and `>` are therefore not interpreted by a shell.
        Prefer passing argv directly from internal callers.
        """

        argv = self._normalize_argv(command)

        if not argv:
            raise ValueError("Command cannot be empty.")

        working_dir = (
            cwd.resolve()
            if cwd is not None
            else self._default_cwd
        )

        if working_dir is None:
            raise ValueError("A working directory is required.")

        if not working_dir.exists():
            raise FileNotFoundError(working_dir)

        if not working_dir.is_dir():
            raise NotADirectoryError(working_dir)

        self._validate_command(argv)

        effective_timeout = (
            self._default_timeout
            if timeout is None
            else timeout
        )

        if effective_timeout <= 0:
            raise ValueError("Timeout must be greater than zero.")

        request = CommandRequest(
            argv=tuple(argv),
            cwd=working_dir,
            timeout=effective_timeout,
            env=env,
        )

        started = time.monotonic()

        try:
            completed = subprocess.run(
                list(request.argv),
                cwd=request.cwd,
                env=request.env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                timeout=request.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - started
            stdout = self._truncate(self._as_text(exc.stdout))
            stderr = self._truncate(self._as_text(exc.stderr))

            return CommandResult(
                success=False,
                argv=request.argv,
                cwd=request.cwd,
                return_code=None,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
                duration_seconds=duration,
                error=f"Command timed out after {request.timeout:g} seconds.",
            )
        except OSError as exc:
            duration = time.monotonic() - started

            return CommandResult(
                success=False,
                argv=request.argv,
                cwd=request.cwd,
                return_code=None,
                duration_seconds=duration,
                error=str(exc),
            )

        duration = time.monotonic() - started

        return CommandResult(
            success=completed.returncode == 0,
            argv=request.argv,
            cwd=request.cwd,
            return_code=completed.returncode,
            stdout=self._truncate(completed.stdout),
            stderr=self._truncate(completed.stderr),
            duration_seconds=duration,
        )

    def _normalize_argv(
        self,
        command: str | list[str] | tuple[str, ...],
    ) -> list[str]:
        if isinstance(command, str):
            # On Windows, posix=False better matches native executable
            # quoting. On POSIX, normal shell-like tokenization is useful.
            return shlex.split(
                command,
                posix=os.name != "nt",
            )

        return [str(part) for part in command]

    def _validate_command(self, argv: list[str]) -> None:
        executable = Path(argv[0]).name.lower()

        if executable in self._BLOCKED_EXECUTABLES:
            raise PermissionError(
                f"Executable '{argv[0]}' is not allowed by CommandRunner."
            )

        # Never treat shell-control tokens as part of an implicit shell
        # command. They can still be passed to a program as ordinary argv,
        # but common shell chaining/redirection is rejected here.
        blocked_tokens = {"&&", "||", "|", ";", ">", ">>", "<"}
        if blocked_tokens.intersection(argv):
            raise PermissionError(
                "Shell operators are not allowed. Pass a program and "
                "its arguments directly."
            )

    def _truncate(self, value: str | bytes | None) -> str:
        if value is None:
            return ""

        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")

        if len(value) <= self._max_output_chars:
            return value

        marker = "\n...[output truncated]..."
        return value[: self._max_output_chars - len(marker)] + marker

    @staticmethod
    def _as_text(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value
