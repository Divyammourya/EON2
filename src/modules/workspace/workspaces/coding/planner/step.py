from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StepType(str, Enum):
    """
    Atomic operations that can appear in an execution plan.

    A planner composes these into a sequence. The executor is
    responsible for performing them.
    """

    OPEN_PROJECT = "open_project"
    READ_FILE = "read_file"
    SEARCH = "search"
    FIND_SYMBOL = "find_symbol"
    INDEX_REPOSITORY = "index_repository"
    INDEX_SYMBOLS = "index_symbols"
    BUILD_CONTEXT = "build_context"
    AI_EDIT = "ai_edit"
    APPLY_PATCH = "apply_patch"
    VALIDATE = "validate"
    RUN_TESTS = "run_tests"
    RUN_COMMAND = "run_command"
    FORMAT = "format"
    LINT = "lint"
    COMMIT = "commit"
    CREATE_FILE = "create_file"
    CREATE_DIRECTORY = "create_directory"
    CUSTOM = "custom"


class PlanStep(BaseModel):
    """
    One executable step within a plan.

    Steps carry a named argument map.
    """

    model_config = ConfigDict(frozen=True)

    type: StepType

    arguments: dict[str, str] = Field(
        default_factory=dict,
    )

    description: str | None = None
