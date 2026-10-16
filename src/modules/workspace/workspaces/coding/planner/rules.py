from __future__ import annotations

from dataclasses import dataclass

from .step import StepType


@dataclass(frozen=True, slots=True)
class PlanningRule:
    """
    Maps a high-level action to a sequence of executable steps.
    """

    action: str
    steps: tuple[StepType, ...]


DEFAULT_RULES: tuple[PlanningRule, ...] = (
    PlanningRule(
        action="open_project",
        steps=(
            StepType.OPEN_PROJECT,
            StepType.INDEX_REPOSITORY,
            StepType.INDEX_SYMBOLS,
        ),
    ),
    PlanningRule(
        action="read_file",
        steps=(StepType.READ_FILE,),
    ),
    PlanningRule(
        action="search",
        steps=(StepType.SEARCH,),
    ),
    PlanningRule(
        action="find_symbol",
        steps=(StepType.FIND_SYMBOL,),
    ),
    PlanningRule(
        action="index",
        steps=(
            StepType.INDEX_REPOSITORY,
            StepType.INDEX_SYMBOLS,
        ),
    ),
    PlanningRule(
        action="ai_edit",
        steps=(
            StepType.FIND_SYMBOL,
            StepType.BUILD_CONTEXT,
            StepType.AI_EDIT,
            StepType.VALIDATE,
            StepType.APPLY_PATCH,
            StepType.INDEX_SYMBOLS,
        ),
    ),
    PlanningRule(
        action="create_file",
        steps=(StepType.CREATE_FILE,),
    ),
    PlanningRule(
        action="create_directory",
        steps=(StepType.CREATE_DIRECTORY,),
    ),
    PlanningRule(
        action="run_command",
        steps=(StepType.RUN_COMMAND,),
    ),
)
