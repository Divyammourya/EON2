"""
Tests for the planner/executor/execution_service trio.

Covers real bugs found while wiring the coding pipeline:

    * planner/__init__.py was empty, so `from .planner import Planner,
      PlanExecutor` in coding_workspace.py could never succeed.

    * execution_service.py imported PlanExecutor from a nonexistent
      top-level `executor.py` instead of `planner/executor.py`.

    * PlanExecutor.execute() discarded every handler's return value,
      so a "successful" plan carried no actual step results.
"""

from __future__ import annotations

import pytest

from src.modules.workspace.workspaces.coding.execution_service import (
    ExecutionService,
)
from src.modules.workspace.workspaces.coding.planner import (
    ExecutionContext,
    ExecutionPlan,
    PlanExecutor,
    Planner,
    PlanStep,
    StepType,
)


class TestPlannerRules:
    def test_open_project_rule(self) -> None:
        planner = Planner()

        plan = planner.create_plan(
            action="open_project",
            arguments={"path": "/some/path"},
        )

        assert plan.step_count() == 3
        assert [s.type for s in plan.steps] == [
            StepType.OPEN_PROJECT,
            StepType.INDEX_REPOSITORY,
            StepType.INDEX_SYMBOLS,
        ]
        assert all(
            s.arguments == {"path": "/some/path"} for s in plan.steps
        )

    def test_unknown_action_produces_empty_plan(self) -> None:
        planner = Planner()

        plan = planner.create_plan(action="not_a_real_action")

        assert plan.is_empty()

    def test_supports_and_available_actions(self) -> None:
        planner = Planner()

        assert planner.supports("search") is True
        assert planner.supports("not_a_real_action") is False
        assert "open_project" in planner.available_actions()


class TestPlanExecutor:
    def test_execute_runs_registered_handlers_in_order(self) -> None:
        executor = PlanExecutor()
        calls: list[str] = []

        executor.register(
            StepType.READ_FILE,
            lambda step, ctx: calls.append("read") or "file-content",
        )
        executor.register(
            StepType.SEARCH,
            lambda step, ctx: calls.append("search") or ["match.py"],
        )

        plan = ExecutionPlan(
            goal="test",
            steps=[
                PlanStep(type=StepType.READ_FILE, arguments={"path": "a.py"}),
                PlanStep(type=StepType.SEARCH, arguments={"query": "query"}),
            ],
        )

        result = executor.execute(plan)

        assert result.success is True
        assert result.completed_steps == 2
        assert calls == ["read", "search"]

    def test_execute_captures_handler_results_in_context(self) -> None:
        executor = PlanExecutor()

        executor.register(
            StepType.SEARCH,
            lambda step, ctx: {"matches": ["a.py", "b.py"]},
        )

        plan = ExecutionPlan(
            goal="test",
            steps=[PlanStep(type=StepType.SEARCH, arguments={"query": "q"})],
        )

        result = executor.execute(plan)

        assert result.context.get("search") == {
            "matches": ["a.py", "b.py"],
        }

    def test_execute_stops_on_missing_handler(self) -> None:
        executor = PlanExecutor()

        executor.register(
            StepType.READ_FILE,
            lambda step, ctx: "ok",
        )

        plan = ExecutionPlan(
            goal="test",
            steps=[
                PlanStep(type=StepType.READ_FILE, arguments={"path": "a.py"}),
                # No handler registered for SEARCH.
                PlanStep(type=StepType.SEARCH, arguments={"query": "q"}),
            ],
        )

        result = executor.execute(plan)

        assert result.success is False
        assert result.completed_steps == 1
        assert "No handler registered" in result.message


class TestExecutionService:
    def test_bridges_planner_output_to_executor(self) -> None:
        executor = PlanExecutor()
        executor.register(
            StepType.SEARCH,
            lambda step, ctx: f"searched for {step.arguments['query']}",
        )

        service = ExecutionService(executor)

        plan = ExecutionPlan(
            goal="search",
            steps=[PlanStep(type=StepType.SEARCH, arguments={"query": "greet"})],
        )

        result = service.execute(plan)

        assert result.success is True
        assert result.context.get("search") == "searched for greet"


class TestExecutionContext:
    def test_get_set_roundtrip(self) -> None:
        context = ExecutionContext()
        context.set("key", "value")

        assert context.get("key") == "value"
        assert context.get("missing", "default") == "default"
