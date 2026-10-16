"""
End-to-end integration tests for the Coding Workspace pipeline:

    Intent -> CodingCommandParser -> Planner -> ExecutionPlan
    -> PlanExecutor -> ExecutionService -> CodingAgent -> Result

Also covers:

    * commands/search.py calling SearchManager.search_text() instead
      of the nonexistent SearchManager.search().

    * commands/edit_symbol.py (previously a missing file) making
      CodingAgent.edit_symbol() and .rollback_last_edit() work.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.modules.intent.models import Intent, IntentType
from src.modules.workspace.workspaces.coding.coding_workspace import (
    CodingWorkspace,
)


SAMPLE_SOURCE = (
    "def greet(name):\n"
    "    return \"hello \" + name\n"
    "\n"
    "\n"
    "class Greeter:\n"
    "    def hello(self):\n"
    "        return \"hi\"\n"
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "sample.py").write_text(SAMPLE_SOURCE, encoding="utf-8")
    return tmp_path


@pytest.fixture
def workspace() -> CodingWorkspace:
    return CodingWorkspace()


def _handle(workspace: CodingWorkspace, text: str):
    return workspace.handle_intent(
        Intent(type=IntentType.FILE, target=text),
    )


class TestCoreParserPipeline:
    def test_open_project_indexes_repository_and_symbols(
        self, workspace: CodingWorkspace, project: Path,
    ) -> None:
        result = _handle(workspace, f"open project {project}")

        assert result.success is True
        assert result.completed_steps == 3
        assert result.context.get("open_project")["success"] is True
        assert result.context.get("index_repository") is not None
        assert result.context.get("index_symbols") is not None

    def test_read_file_returns_content(
        self, workspace: CodingWorkspace, project: Path,
    ) -> None:
        _handle(workspace, f"open project {project}")

        result = _handle(workspace, "read sample.py")

        assert result.success is True
        content = result.context.get("read_file")["content"]
        assert "def greet" in content

    def test_search_returns_matching_files(
        self, workspace: CodingWorkspace, project: Path,
    ) -> None:
        _handle(workspace, f"open project {project}")

        result = _handle(workspace, "search greet")

        assert result.success is True
        matches = result.context.get("search")["matches"]
        assert any("sample.py" in m for m in matches)

    def test_find_symbol_locates_definition(
        self, workspace: CodingWorkspace, project: Path,
    ) -> None:
        _handle(workspace, f"open project {project}")
        _handle(workspace, "index project")

        result = _handle(workspace, "where is greet defined")

        assert result.success is True
        symbols = result.context.get("find_symbol")
        assert len(symbols) == 1
        assert symbols[0].name == "greet"

    def test_unparseable_input_falls_back_to_agent_handle(
        self, workspace: CodingWorkspace, project: Path,
    ) -> None:
        _handle(workspace, f"open project {project}")

        # No parser rule matches this -> falls back to agent.handle().
        result = _handle(workspace, "what is the meaning of life")

        assert result["workspace"] == "coding"
        assert result["project_open"] is True


class TestEditAndRollback:
    def test_edit_symbol_applies_and_rollback_restores(
        self, workspace: CodingWorkspace, project: Path,
    ) -> None:
        workspace.agent.open_project(str(project))

        edit_result = workspace.agent.edit_symbol(
            "sample.py",
            "greet",
            'def greet(name):\n    return f"hey {name}"',
        )

        assert edit_result["success"] is True
        assert (
            'f"hey {name}"'
            in (project / "sample.py").read_text(encoding="utf-8")
        )

        rollback_result = workspace.agent.rollback_last_edit()

        assert rollback_result["success"] is True
        assert (
            (project / "sample.py").read_text(encoding="utf-8")
            == SAMPLE_SOURCE
        )

    def test_rollback_with_nothing_to_undo(
        self, workspace: CodingWorkspace, project: Path,
    ) -> None:
        workspace.agent.open_project(str(project))

        result = workspace.agent.rollback_last_edit()

        assert result["success"] is False
