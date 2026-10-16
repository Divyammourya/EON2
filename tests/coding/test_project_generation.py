"""
Tests for the project-generation capability added this session:

    * FileManager.create_directory
    * CreateFileCommand / CreateDirectoryCommand
    * CodingAgent.create_file / create_directory / create_project
    * The CREATE_FILE / CREATE_DIRECTORY planner rule + executor wiring
    * End-to-end: Intent -> parser -> CodingWorkspace.create_project
      -> real files on disk

No real AI provider is used. CodingAgent.create_project() is exercised
with a fake ProjectScaffolder (matching ProjectScaffolder's public
interface) so these tests are deterministic and don't need Ollama
running - mirroring how AICodeEditor is not exercised through a real
model in test_code_edit.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.modules.intent.models import Intent, IntentType
from src.modules.workspace.workspaces.coding.coding_workspace import (
    CodingWorkspace,
)
from src.modules.workspace.workspaces.coding.file_manager import (
    FileManager,
)
from src.modules.workspace.workspaces.coding.project_manager import (
    ProjectManager,
)
from src.modules.workspace.workspaces.coding.project_scaffolder import (
    ScaffoldFile,
    ScaffoldResult,
)
from src.modules.workspace.workspaces.coding.planner import (
    Planner,
    StepType,
)


class FakeScaffolder:
    """Stands in for ProjectScaffolder without calling any AI provider."""

    def __init__(self, result: ScaffoldResult) -> None:
        self._result = result
        self.calls: list[str] = []

    def generate(self, description: str) -> ScaffoldResult:
        self.calls.append(description)
        return self._result


@pytest.fixture
def project_manager(tmp_path: Path) -> ProjectManager:
    manager = ProjectManager()
    manager.open_project(tmp_path)
    return manager


@pytest.fixture
def file_manager(project_manager: ProjectManager) -> FileManager:
    return FileManager(project_manager)


class TestFileManagerCreateDirectory:
    def test_creates_nested_directory(
        self, file_manager: FileManager, tmp_path: Path,
    ) -> None:
        file_manager.create_directory("src/app")

        assert (tmp_path / "src" / "app").is_dir()

    def test_is_idempotent(
        self, file_manager: FileManager, tmp_path: Path,
    ) -> None:
        file_manager.create_directory("src")
        file_manager.create_directory("src")  # should not raise

        assert (tmp_path / "src").is_dir()


class TestPlannerRulesForFileCreation:
    def test_create_file_rule(self) -> None:
        planner = Planner()

        plan = planner.create_plan(
            action="create_file",
            arguments={"path": "a.py", "content": "print('hi')"},
        )

        assert plan.step_count() == 1
        assert plan.steps[0].type == StepType.CREATE_FILE
        assert plan.steps[0].arguments == {
            "path": "a.py",
            "content": "print('hi')",
        }

    def test_create_directory_rule(self) -> None:
        planner = Planner()

        plan = planner.create_plan(
            action="create_directory",
            arguments={"path": "src"},
        )

        assert plan.step_count() == 1
        assert plan.steps[0].type == StepType.CREATE_DIRECTORY


class TestCodingWorkspaceFileCreation:
    @pytest.fixture
    def workspace(self) -> CodingWorkspace:
        return CodingWorkspace()

    def _handle(self, workspace: CodingWorkspace, text: str):
        return workspace.handle_intent(
            Intent(type=IntentType.FILE, target=text),
        )

    def test_create_file_writes_to_disk(
        self, workspace: CodingWorkspace, tmp_path: Path,
    ) -> None:
        self._handle(workspace, f"open project {tmp_path}")

        result = self._handle(workspace, "create file notes.txt")

        assert result.success is True
        step_result = result.context.get("create_file")
        assert step_result["success"] is True
        assert (tmp_path / "notes.txt").exists()
        assert (tmp_path / "notes.txt").read_text() == ""

    def test_create_directory_creates_dir(
        self, workspace: CodingWorkspace, tmp_path: Path,
    ) -> None:
        self._handle(workspace, f"open project {tmp_path}")

        result = self._handle(workspace, "create folder src")

        assert result.success is True
        assert (tmp_path / "src").is_dir()

    def test_create_file_without_open_project_reports_failure(
        self, workspace: CodingWorkspace,
    ) -> None:
        result = self._handle(workspace, "create file notes.txt")

        step_result = result.context.get("create_file")
        assert step_result["success"] is False
        assert "No project" in step_result["error"]


class TestCodingAgentCreateProject:
    @pytest.fixture
    def workspace(self) -> CodingWorkspace:
        return CodingWorkspace()

    def test_scaffold_creates_every_file(
        self, workspace: CodingWorkspace, tmp_path: Path,
    ) -> None:
        workspace.agent.open_project(str(tmp_path))

        fake = FakeScaffolder(
            ScaffoldResult(
                success=True,
                files=[
                    ScaffoldFile(
                        path="main.py",
                        content="print('hello')\n",
                    ),
                    ScaffoldFile(
                        path="README.md",
                        content="# demo\n",
                    ),
                    ScaffoldFile(
                        path="app/__init__.py",
                        content="",
                    ),
                ],
            ),
        )
        workspace.agent.scaffolder = fake

        result = workspace.agent.create_project(
            "a tiny demo project",
        )

        assert result["success"] is True
        assert result["files_created"] == [
            "main.py",
            "README.md",
            "app/__init__.py",
        ]
        assert result["files_failed"] == []
        assert (tmp_path / "main.py").read_text() == "print('hello')\n"
        assert (tmp_path / "README.md").read_text() == "# demo\n"
        # Nested file created its parent directory automatically.
        assert (tmp_path / "app" / "__init__.py").exists()

    def test_scaffold_failure_writes_nothing(
        self, workspace: CodingWorkspace, tmp_path: Path,
    ) -> None:
        workspace.agent.open_project(str(tmp_path))

        fake = FakeScaffolder(
            ScaffoldResult(
                success=False,
                files=[],
                message="The model did not return any files to create.",
            ),
        )
        workspace.agent.scaffolder = fake

        result = workspace.agent.create_project("garbage in")

        assert result["success"] is False
        assert result["files_created"] == []
        assert "did not return any files" in result["error"]
        assert list(tmp_path.iterdir()) == []

    def test_scaffold_partial_failure_reports_and_stops(
        self, workspace: CodingWorkspace, tmp_path: Path,
    ) -> None:
        workspace.agent.open_project(str(tmp_path))

        fake = FakeScaffolder(
            ScaffoldResult(
                success=True,
                files=[
                    ScaffoldFile(path="ok.py", content="x = 1\n"),
                    # Escapes the project root -> FileManager raises,
                    # CreateFileCommand converts that into a failure
                    # result rather than an unhandled exception.
                    ScaffoldFile(
                        path="../outside.py",
                        content="bad",
                    ),
                    ScaffoldFile(path="never_reached.py", content=""),
                ],
            ),
        )
        workspace.agent.scaffolder = fake

        result = workspace.agent.create_project("a project")

        assert result["success"] is False
        assert result["files_created"] == ["ok.py"]
        assert len(result["files_failed"]) == 1
        assert result["files_failed"][0]["path"] == "../outside.py"
        assert result["files_skipped"] == ["never_reached.py"]
        assert (tmp_path / "ok.py").exists()
        assert not (tmp_path / "outside.py").exists()

    def test_create_project_routes_through_workspace_intent(
        self, workspace: CodingWorkspace, tmp_path: Path,
    ) -> None:
        workspace.agent.open_project(str(tmp_path))

        fake = FakeScaffolder(
            ScaffoldResult(
                success=True,
                files=[ScaffoldFile(path="main.py", content="pass\n")],
            ),
        )
        workspace.agent.scaffolder = fake

        result = workspace.handle_intent(
            Intent(
                type=IntentType.FILE,
                target="Create a Python project with a main file",
            ),
        )

        assert result["success"] is True
        assert result["files_created"] == ["main.py"]
        assert (tmp_path / "main.py").exists()
        assert fake.calls == [
            "Create a Python project with a main file",
        ]
