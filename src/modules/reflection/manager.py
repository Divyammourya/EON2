"""
Reflection Manager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.modules.execution.models import ExecutionResult
from src.modules.reflection.models import ReflectionResult
from src.modules.reflection.reflector import Reflector

if TYPE_CHECKING:
    from src.modules.memory.service import MemoryService


class ReflectionManager:
    """
    High-level interface for reflection.
    """

    def __init__(self, memory: "MemoryService | None" = None) -> None:
        self._reflector = Reflector(memory=memory)

    def reflect(
        self,
        execution: ExecutionResult,
    ) -> ReflectionResult:
        """
        Reflect on a completed execution.
        """

        return self._reflector.reflect(
            execution,
        )
