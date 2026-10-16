from __future__ import annotations

import sys
from pathlib import Path

from src.modules.intent.models import Intent, IntentType
from src.modules.workspace.workspaces.coding.coding_workspace import (
    CodingWorkspace,
)


def test_run_command_through_workspace(tmp_path: Path) -> None:
    workspace = CodingWorkspace()

    opened = workspace.handle_intent(
        Intent(
            type=IntentType.OPEN_APP,
            target=f"open project {tmp_path}",
        ),
    )
    assert opened.success is True

    result = workspace.handle_intent(
        Intent(
            type=IntentType.SYSTEM,
            target=f"run {sys.executable} -c \"print('hello from EON')\"",
        ),
    )

    assert result.success is True

    command_result = result.context.get("run_command")
    assert command_result["success"] is True
    assert command_result["return_code"] == 0
    assert "hello from EON" in command_result["stdout"]


def test_run_command_without_project_fails(tmp_path: Path) -> None:
    workspace = CodingWorkspace()

    result = workspace.handle_intent(
        Intent(
            type=IntentType.SYSTEM,
            target="run python --version",
        ),
    )

    command_result = result.context.get("run_command")
    assert command_result["success"] is False
    assert "No project" in command_result["error"]
