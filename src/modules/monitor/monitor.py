"""
Execution Monitor.
"""

from __future__ import annotations

from src.modules.execution.models import ExecutionResult
from src.modules.monitor.models import MonitorResult


class Monitor:
    """
    Observes execution results and produces a summary.
    """

    def monitor(
        self,
        execution: ExecutionResult,
    ) -> MonitorResult:
        """
        Monitor an executed plan.
        """

        if execution.success:
            message = "Execution completed successfully."
        else:
            message = "Execution completed with failures."

        return MonitorResult(
            execution=execution,
            success=execution.success,
            message=message,
        )
