from __future__ import annotations

from src.modules.intent.models import Intent, IntentType
from src.modules.workspace.workspaces.base.base_workspace import BaseWorkspace

from .agent import CodingAgent
from .ai_editor import AICodeEditor
from .code_edit import CodeEditEngine
from .context_builder import SymbolContextBuilder
from .editor_session import EditorSession
from .file_manager import FileManager
from .git_manager import GitManager
from .nlp_parser import CodingCommandParser
from .patch_engine import PatchBuilder, PatchEngine
from .project_manager import ProjectManager
from .repository_indexer import RepositoryIndexer
from .search_manager import SearchManager
from .symbol_indexer import SymbolIndexer
from .planner import Planner, PlanExecutor
from .planner.step import StepType
from .execution_service import ExecutionService
from .execution import CommandRunner

class CodingWorkspace(BaseWorkspace):
    """
    Workspace responsible for software development tasks.
    """

    def __init__(self) -> None:
        super().__init__()

        # Services owned by this workspace.
        self.project_manager = ProjectManager()

        self.file_manager = FileManager(
            self.project_manager,
        )

        self.editor = EditorSession()

        self.git = GitManager(
            self.project_manager,
        )

        self.search = SearchManager(
            self.project_manager,
        )

        self.indexer = RepositoryIndexer(
            self.project_manager,
        )

        self.symbol_indexer = SymbolIndexer(
            self.indexer,
        )

        self.edit_engine = CodeEditEngine()

        self.patch_engine = PatchEngine()

        self.patch_builder = PatchBuilder()

        self.ai_editor = AICodeEditor()

        self.context_builder = SymbolContextBuilder(
            self.indexer,
            self.symbol_indexer,
        )

        self.parser = CodingCommandParser()

        self.planner = Planner()
        self.executor = PlanExecutor()

        self.execution = ExecutionService(
            self.executor,
        )

        self.command_runner = CommandRunner(
            default_cwd=self.project_manager.project_root,
        )

        self.agent = CodingAgent(
            project=self.project_manager,
            files=self.file_manager,
            editor=self.editor,
            git=self.git,
            search=self.search,
            indexer=self.indexer,
            symbols=self.symbol_indexer,
            edit_engine=self.edit_engine,
            patch_engine=self.patch_engine,
            patch_builder=self.patch_builder,
            ai_editor=self.ai_editor,
            context_builder=self.context_builder,
            planner=self.planner,
            execution=self.execution,
            command_runner=self.command_runner,
        )

        self._register_handlers()

        self._metadata.id = "coding"
        self._metadata.name = "Coding Workspace"
        self._metadata.description = (
            "Workspace for software development."
        )
        self._metadata.icon = "💻"
        self._metadata.category = "development"

    def can_handle(self, intent: Intent) -> bool:
        return intent.type in {
            IntentType.OPEN_APP,
            IntentType.FILE,
            IntentType.SYSTEM,
        }

    def handle_intent(self, intent: Intent) -> dict:
        """
        Main entry point into the Coding Workspace.
        """

        try:

            parsed = self.parser.parse(
                intent.target or "",
            )

            if parsed is None:
                return self.agent.handle(intent)

            # create_project is AI-driven and produces a variable
            # number of files, so it isn't a fixed step-sequence rule
            # like the others - it's handled as its own CodingAgent
            # entry point, which internally still runs every file it
            # creates through this same Planner/ExecutionService.
            if parsed.action == "create_project":
                return self.agent.create_project(
                    parsed.arguments.get("description", ""),
                )

            plan = self.planner.create_plan(
                action=parsed.action,
                arguments=parsed.arguments,
            )

            return self.execution.execute(plan)

        except Exception as exc:

            return {
                "success": False,
                "error": str(exc),
            }

    @staticmethod
    def _command_timeout(step) -> float | None:
        raw = step.arguments.get("timeout")
        if raw is None or raw == "":
            return None

        try:
            value = float(raw)
        except ValueError as exc:
            raise ValueError("Command timeout must be numeric.") from exc

        if value <= 0:
            raise ValueError("Command timeout must be greater than zero.")

        return value

    def _register_handlers(self) -> None:
        """
        Register executor handlers.

        Each planning step is mapped to the method that performs it.
        """

        self.executor.register(
            StepType.OPEN_PROJECT,
            lambda step, ctx: self.agent.open_project(
                step.arguments.get("path", ""),
            ),
        )

        self.executor.register(
            StepType.READ_FILE,
            lambda step, ctx: self.agent.read_file(
                step.arguments.get("path", ""),
            ),
        )

        self.executor.register(
            StepType.SEARCH,
            lambda step, ctx: self.agent.search_project(
                step.arguments.get("query", ""),
            ),
        )

        self.executor.register(
            StepType.FIND_SYMBOL,
            lambda step, ctx: self.agent.find_symbol(
                step.arguments.get("name", ""),
            ),
        )

        self.executor.register(
            StepType.INDEX_REPOSITORY,
            lambda step, ctx: self.agent.index_repository(),
        )

        self.executor.register(
            StepType.INDEX_SYMBOLS,
            lambda step, ctx: self.agent.index_symbols(),
        )


        self.executor.register(
            StepType.RUN_COMMAND,
            lambda step, ctx: self.agent.run_command(
                step.arguments.get("command", ""),
                timeout=self._command_timeout(step),
            ),
        )

        self.executor.register(
            StepType.CREATE_FILE,
            lambda step, ctx: self.agent.create_file(
                step.arguments.get("path", ""),
                step.arguments.get("content", ""),
            ),
        )

        self.executor.register(
            StepType.CREATE_DIRECTORY,
            lambda step, ctx: self.agent.create_directory(
                step.arguments.get("path", ""),
            ),
        )
