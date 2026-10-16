from __future__ import annotations

from src.modules.intent.models import Intent

from .project_manager import ProjectManager
from .file_manager import FileManager
from .editor_session import EditorSession
from .git_manager import GitManager
from .search_manager import SearchManager
from .repository_indexer import RepositoryIndexer
from .symbol_indexer import SymbolIndexer
from .models import RepositoryIndex, Symbol
from .ai_editor import AICodeEditor
from .code_edit import CodeEditEngine
from .context_builder import SymbolContextBuilder
from .patch_engine import PatchBuilder, PatchEngine
from .planner import Planner, PlanExecutor
from .execution_service import ExecutionService
from .execution import CommandRunner
from .project_scaffolder import ProjectScaffolder
from .commands import (
    CommandDispatcher,
    OpenProjectCommand,
    ReadFileCommand,
    SearchCommand,
    EditSymbolCommand,
    AIEditSymbolCommand,
    CreateFileCommand,
    CreateDirectoryCommand,
)

class CodingAgent:
    """
    High-level coordinator for the Coding Workspace.

    The CodingAgent does not perform filesystem operations itself.
    Instead, it coordinates the managers that own those responsibilities.

    Later this class will also communicate with:
        • AI models
        • Planning
        • Terminal execution
        • Diff generation
        • Code editing
        • Testing
        • Git workflows
    """

    def __init__(
        self,
        *,
        project: ProjectManager,
        files: FileManager,
        editor: EditorSession,
        git: GitManager,
        search: SearchManager,
        indexer: RepositoryIndexer,
        symbols: SymbolIndexer,
        edit_engine: CodeEditEngine | None = None,
        patch_engine: PatchEngine | None = None,
        patch_builder: PatchBuilder | None = None,
        ai_editor: AICodeEditor | None = None,
        context_builder: SymbolContextBuilder | None = None,
        planner: Planner | None = None,
        execution: ExecutionService | None = None,
        scaffolder: ProjectScaffolder | None = None,
        command_runner: CommandRunner | None = None,
    ) -> None:

        self.project = project
        self.files = files
        self.editor = editor
        self.git = git
        self.search = search
        self.indexer = indexer
        self.symbols = symbols
        self.dispatcher = CommandDispatcher()

        # Editing pipeline. Optional/DI'd so existing callers that
        # construct a CodingAgent with only the original arguments
        # keep working unchanged, while CodingWorkspace (or a future
        # Planner) can inject shared instances instead.
        self.edit_engine = (
            edit_engine if edit_engine is not None else CodeEditEngine()
        )
        self.patch_engine = (
            patch_engine if patch_engine is not None else PatchEngine()
        )
        self.patch_builder = (
            patch_builder if patch_builder is not None else PatchBuilder()
        )
        self.ai_editor = (
            ai_editor if ai_editor is not None else AICodeEditor()
        )
        self.context_builder = (
            context_builder
            if context_builder is not None
            else SymbolContextBuilder(self.indexer, self.symbols)
        )

        # Used by create_project() to run each scaffolded file through
        # the same Planner -> PlanExecutor pipeline every other action
        # goes through. CodingWorkspace injects its own shared planner
        # and execution service (with handlers already registered);
        # the defaults here exist only so a standalone CodingAgent
        # doesn't crash to construct, matching the DI pattern above.
        # Without an injected, handler-registered ExecutionService,
        # create_project() will report every file as failed rather
        # than silently doing nothing.
        self.planner = (
            planner if planner is not None else Planner()
        )
        self.execution = (
            execution
            if execution is not None
            else ExecutionService(PlanExecutor())
        )
        self.scaffolder = (
            scaffolder if scaffolder is not None else ProjectScaffolder()
        )

        self.command_runner = (
            command_runner
            if command_runner is not None
            else CommandRunner(
                default_cwd=self.project.project_root,
            )
        )

    def run_command(
        self,
        command: str,
        *,
        timeout: float | None = None,
    ) -> dict:
        """Run a developer command in the currently open project."""

        if not self.project.has_project():
            return {
                "success": False,
                "command": command,
                "error": "No project is currently open.",
            }

        # Keep the runner's cwd synchronized with the active project.
        self.command_runner._default_cwd = self.project.project_root

        result = self.command_runner.run(
            command,
            timeout=timeout,
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

    def index_repository(self) -> RepositoryIndex:
        """
        Explicitly (re)build the repository index for the current project.

        Exposed as its own method, separate from `handle()`, because a
        future Planner / tool-calling loop will need to trigger indexing
        as a discrete step — e.g. "index the repo" as one action in a
        multi-step plan — rather than only as a side effect of handling
        a generic intent.
        """

        return self.indexer.build_index()

    def index_symbols(self) -> dict:
        """
        Explicitly (re)build the symbol index for the current project.

        Depends on the repository index being current — callers that
        want a fully fresh view should call `index_repository()` first.
        Kept as its own method for the same reason `index_repository()`
        is: a future planner will need "index symbols" as a discrete,
        callable step.
        """

        return self.symbols.build_index()

    def find_symbol(self, name: str) -> list[Symbol]:
        """
        Look up a symbol by exact name across the indexed project.
        """

        return self.symbols.find_symbol(name)

    def handle(self, intent: Intent):
        """
        Entry point for every coding intent.

        For now this simply returns a snapshot of the workspace.

        Later this becomes the main reasoning loop.
        """

        project_open = self.project.has_project()

        return {
            "workspace": "coding",
            "intent": intent.type.value,
            "target": intent.target,
            "project_open": project_open,
            "git_repository": self.git.is_repository(),
            "active_file": (
                str(self.editor.active_file)
                if self.editor.active_file
                else None
            ),
            "indexed_files": (
                self.indexer.get_index().file_count()
                if project_open
                else None
            ),
            "indexed_symbols": (
                sum(
                    len(file_symbols)
                    for file_symbols in self.symbols.get_index().values()
                )
                if project_open
                else None
            ),
        }

    def open_project(self, path: str):
        command = OpenProjectCommand(
            self.project,
            path,
        )
        return self.dispatcher.dispatch(command)


    def read_file(self, path: str):
        command = ReadFileCommand(
            self.files,
            self.editor,
            path,
        )
        return self.dispatcher.dispatch(command)


    def search_project(self, query: str):
        command = SearchCommand(
            self.search,
            query,
        )
        return self.dispatcher.dispatch(command)

    def edit_symbol(self, file: str, symbol: str, replacement: str):
        """
        Replace a class/function/method inside a project file with a
        literal replacement string.

        Runs the edit through the CodeEditEngine (locate, format,
        validate) and then the PatchEngine (validate, apply, record
        for rollback). Nothing is written to disk unless both stages
        succeed.
        """

        command = EditSymbolCommand(
            self.files,
            self.edit_engine,
            self.patch_engine,
            self.patch_builder,
            file,
            symbol,
            replacement,
        )
        return self.dispatcher.dispatch(command)

    def ai_edit_symbol(self, file: str, symbol: str, instruction: str):
        """
        Replace a class/function/method from a natural-language
        instruction instead of a literal replacement string.

        Gathers cross-file context (imports, sibling symbols, callers)
        via the SymbolContextBuilder so the AICodeEditor isn't
        reasoning about the symbol in isolation, then routes the
        generated replacement through the exact same edit_symbol
        pipeline — format, validate, patch, rollback — as a manually
        supplied replacement. This is the entry point a future
        Planner / tool-calling loop should call for autonomous code
        edits.
        """

        command = AIEditSymbolCommand(
            self.files,
            self.edit_engine,
            self.patch_engine,
            self.patch_builder,
            self.ai_editor,
            self.context_builder,
            file,
            symbol,
            instruction,
        )
        return self.dispatcher.dispatch(command)

    def create_file(self, path: str, content: str = "") -> dict:
        """
        Create (or overwrite) a single project file with literal
        content.
        """

        command = CreateFileCommand(
            self.files,
            path,
            content,
        )
        return self.dispatcher.dispatch(command)

    def create_directory(self, path: str) -> dict:
        """
        Create a single project directory (and any missing parents).
        """

        command = CreateDirectoryCommand(
            self.files,
            path,
        )
        return self.dispatcher.dispatch(command)

    def create_project(self, description: str) -> dict:
        """
        Scaffold a new project from a natural-language description.

        Asks the AI (via ProjectScaffolder) for a list of files with
        content, then creates each one through the same
        Planner -> PlanExecutor -> ExecutionService pipeline every
        other action in this workspace goes through - one
        single-step "create_file" plan per file, run in sequence,
        rather than one large plan with many CREATE_FILE steps.

        That's a deliberate choice, not a shortcut: PlanExecutor
        records each step's result in ExecutionContext keyed by
        step *type* (see planner/executor.py), so multiple CREATE_FILE
        steps inside one plan would overwrite each other's recorded
        result and make partial-failure reporting unreliable. Running
        one file per plan keeps every result distinct without
        touching the executor, which this session treats as frozen.

        Stops at the first file that fails to write and reports
        exactly what succeeded, what failed, and what was never
        attempted - never a silently half-written project. If the AI
        doesn't return a usable file list at all, nothing is written.
        """

        scaffold = self.scaffolder.generate(description)

        if not scaffold.success:
            return {
                "success": False,
                "description": description,
                "files_created": [],
                "files_failed": [],
                "files_skipped": [],
                "error": scaffold.message,
            }

        created: list[str] = []
        failed: list[dict] = []

        for index, file in enumerate(scaffold.files):

            plan = self.planner.create_plan(
                action="create_file",
                arguments={
                    "path": file.path,
                    "content": file.content,
                },
            )

            result = self.execution.execute(plan)

            step_result = (
                result.context.get("create_file")
                if result.success
                else None
            )

            if (
                result.success
                and isinstance(step_result, dict)
                and step_result.get("success")
            ):
                created.append(file.path)
                continue

            error = (
                step_result.get("error")
                if isinstance(step_result, dict)
                else result.message
            )
            failed.append({"path": file.path, "error": error})
            break

        attempted = len(created) + len(failed)
        skipped = [file.path for file in scaffold.files[attempted:]]

        success = bool(created) and not failed

        return {
            "success": success,
            "description": description,
            "files_created": created,
            "files_failed": failed,
            "files_skipped": skipped,
            "message": (
                f"Created {len(created)} file(s)."
                if success
                else (
                    f"Created {len(created)} file(s), then stopped: "
                    f"{failed[0]['error']}"
                )
            ),
        }

    def rollback_last_edit(self) -> dict:
        """
        Undo the most recently applied edit.
        """

        result = self.patch_engine.rollback.rollback_last()

        if result is None:
            return {
                "success": False,
                "message": "Nothing to roll back.",
            }

        return {
            "success": True,
            "changed_files": result.changed_files,
            "message": f"Rolled back {result.changed_files} file(s).",
        }
