"""
State Management Service for EON.

Tracks the current lifecycle state of the application.
"""

from __future__ import annotations

from enum import Enum

from src.core.logger import get_logger

logger = get_logger("State")


class EONState(Enum):
    """Possible runtime states for EON."""

    OFFLINE = "OFFLINE"
    STARTING = "STARTING"
    READY = "READY"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    EXECUTING = "EXECUTING"
    SPEAKING = "SPEAKING"
    SHUTTING_DOWN = "SHUTTING_DOWN"


class StateManager:
    """Manages the current state of EON."""

    def __init__(self) -> None:
        self._current_state = EONState.STARTING

        logger.info(
            "Initial state: %s",
            self._current_state.value,
        )

    @property
    def current_state(self) -> EONState:
        """Return the current state."""

        return self._current_state

    def set_state(self, new_state: EONState) -> None:
        """Change the current state."""

        if new_state == self._current_state:
            return

        previous = self._current_state

        self._current_state = new_state

        logger.info(
            "State changed: %s → %s",
            previous.value,
            new_state.value,
        )
