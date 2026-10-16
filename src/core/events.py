"""
Event Bus Service for EON.

Provides publish/subscribe communication between modules.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from src.core.logger import get_logger

logger = get_logger("Events")


EventCallback = Callable[[dict[str, Any]], None]


class EventBus:
    """Simple publish/subscribe event bus."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventCallback]] = defaultdict(list)

        logger.info("Event Bus initialized.")

    def subscribe(
        self,
        event_name: str,
        callback: EventCallback,
    ) -> None:
        """Subscribe a callback to an event."""

        self._subscribers[event_name].append(callback)

        logger.info(
            "Subscribed '%s' to event '%s'",
            callback.__name__,
            event_name,
        )

    def publish(
        self,
        event_name: str,
        data: dict[str, Any],
    ) -> None:
        """Publish an event."""

        logger.info(
            "Publishing event '%s'",
            event_name,
        )

        for callback in self._subscribers[event_name]:
            callback(data)
