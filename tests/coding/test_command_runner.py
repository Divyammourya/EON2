from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.modules.workspace.workspaces.coding.execution import (
    CommandRunner,
)


def test_runs_process_in_project_directory(tmp_path: Path) -> None:
    runner = CommandRunner(default_cwd=tmp_path)

    result = runner.run(
        [
            sys.executable,
            "-c",
            "import os; print(os.getcwd())",
        ],
    )

    assert result.success is True
    assert result.return_code == 0
    assert result.stdout.strip() == str(tmp_path)


def test_captures_stderr_and_nonzero_exit(tmp_path: Path) -> None:
    runner = CommandRunner(default_cwd=tmp_path)

    result = runner.run(
        [
            sys.executable,
            "-c",
            "import sys; print('bad', file=sys.stderr); sys.exit(3)",
        ],
    )

    assert result.success is False
    assert result.return_code == 3
    assert "bad" in result.stderr


def test_timeout_is_reported(tmp_path: Path) -> None:
    runner = CommandRunner(
        default_cwd=tmp_path,
        default_timeout=0.05,
    )

    result = runner.run(
        [
            sys.executable,
            "-c",
            "import time; time.sleep(1)",
        ],
    )

    assert result.success is False
    assert result.timed_out is True
    assert result.error is not None


def test_shell_operators_are_rejected(tmp_path: Path) -> None:
    runner = CommandRunner(default_cwd=tmp_path)

    with pytest.raises(PermissionError):
        runner.run(
            [
                sys.executable,
                "-c",
                "print('ok')",
                "&&",
                "echo",
                "bad",
            ],
        )


def test_empty_command_is_rejected(tmp_path: Path) -> None:
    runner = CommandRunner(default_cwd=tmp_path)

    with pytest.raises(ValueError):
        runner.run("")
