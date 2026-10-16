from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .step import PlanStep


class ExecutionContext(BaseModel):
    """
    Shared state accumulated while executing a plan.

    Steps may write values here that later steps depend on.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    data: dict[str, object] = Field(
        default_factory=dict,
    )

    def get(
        self,
        key: str,
        default: object | None = None,
    ) -> object | None:
        return self.data.get(key, default)

    def set(
        self,
        key: str,
        value: object,
    ) -> None:
        self.data[key] = value


class ExecutionPlan(BaseModel):
    """
    Ordered collection of executable steps.

    Produced by the Planner and consumed by the Executor.
    """

    model_config = ConfigDict(
        frozen=True,
    )

    goal: str

    steps: list[PlanStep] = Field(
        default_factory=list,
    )

    def is_empty(self) -> bool:
        return len(self.steps) == 0

    def step_count(self) -> int:
        return len(self.steps)


class PlanResult(BaseModel):
    """
    Result returned after executing a plan.
    """

    model_config = ConfigDict()

    success: bool

    completed_steps: int = 0

    message: str = ""

    context: ExecutionContext = Field(
        default_factory=ExecutionContext,
    )
