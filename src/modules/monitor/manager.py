"""
Monitor Manager.

Public interface for execution and ambient monitoring.
"""

from __future__ import annotations

from src.modules.execution.models import ExecutionResult
from src.modules.monitor.ambient import (
    AmbientMonitor,
    CalendarAmbientSource,
    DownloadAmbientSource,
    HungWindowAmbientSource,
)
from src.modules.monitor.config import AmbientMonitorConfig
from src.modules.monitor.models import AmbientSignal, MonitorResult
from src.modules.monitor.monitor import Monitor


class MonitorManager:
    """
    High-level interface for monitoring execution and ambient state.
    """

    def __init__(
        self,
        ambient_config: AmbientMonitorConfig | None = None,
        calendar_tool=None,
    ) -> None:
        self._monitor = Monitor()
        self._ambient_config = ambient_config or AmbientMonitorConfig()
        self._ambient = AmbientMonitor(
            config=self._ambient_config,
            sources=self._build_ambient_sources(calendar_tool),
        )

    def monitor(
        self,
        execution: ExecutionResult,
    ) -> MonitorResult:
        """
        Monitor an execution result.
        """

        return self._monitor.monitor(
            execution,
        )

    def scan_ambient(self) -> list[AmbientSignal]:
        """
        Scan for things EON should notice unprompted.
        """

        return self._ambient.scan()

    @property
    def ambient_check_interval_seconds(self) -> float:
        return self._ambient_config.check_interval_seconds

    def _build_ambient_sources(self, calendar_tool) -> list:
        sources = []

        if self._ambient_config.downloads_enabled:
            sources.append(
                DownloadAmbientSource(
                    downloads_path=self._ambient_config.downloads_path,
                )
            )

        if self._ambient_config.hung_window_enabled:
            sources.append(HungWindowAmbientSource())

        if self._ambient_config.calendar_enabled and calendar_tool is not None:
            sources.append(
                CalendarAmbientSource(
                    calendar_tool=calendar_tool,
                    warning_minutes=self._ambient_config.calendar_warning_minutes,
                    lookahead_minutes=self._ambient_config.calendar_lookahead_minutes,
                )
            )

        return sources
