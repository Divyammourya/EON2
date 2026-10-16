"""
Memory Events.

Defines all event names used by the Memory subsystem.
"""

from __future__ import annotations

from enum import Enum


class MemoryEvent(Enum):
    """
    Events published by the Memory subsystem.
    """

    CREATED = "memory.created"

    UPDATED = "memory.updated"

    DELETED = "memory.deleted"

    RETRIEVED = "memory.retrieved"

    SEARCHED = "memory.searched"

    CLEARED = "memory.cleared"

    INITIALIZED = "memory.initialized"

    SHUTDOWN = "memory.shutdown"
