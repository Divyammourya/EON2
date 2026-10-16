"""
Tool models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ToolResult:
    """Result returned by a tool."""

    success: bool
    message: str
