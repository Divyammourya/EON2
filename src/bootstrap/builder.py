"""
Application Builder.

Creates the complete EON application.
"""

from __future__ import annotations

from src.bootstrap.application import Application
from src.bootstrap.modules import register_modules
from src.bootstrap.services import register_services

from src.core.container import ServiceContainer
from src.core.engine import Engine
from src.core.logger import get_logger

from src.modules.automation.weather import WeatherTool
from src.modules.briefing.morning import MorningBriefing
from src.modules.conversation.manager import ConversationManager
from src.modules.workspace.workspaces.coding.mode import CodingMode
from src.modules.workspace.workspaces.coding.session import (
    DEFAULT_WORKSPACE_ROOT,
)
from src.ui.coding.service import CodingWindowService

from typing import Any


logger = get_logger("Bootstrap")


def _build_weather_tool(config) -> WeatherTool:
    """Builds a weather tool from the configured location.

    ``register_services`` builds its own copy to hand to the tool
    registry, where the model can call it by name. This one is for the
    morning briefing, which needs the structured readings rather than a
    tool the model invokes.

    Args:
        config: The loaded configuration.

    Returns:
        A weather tool pointed at the user's location.
    """
    kwargs: dict[str, Any] = {}

    location_name = config.get("weather_location_name")
    latitude = config.get("weather_latitude")
    longitude = config.get("weather_longitude")

    if location_name:
        kwargs["default_location_name"] = str(location_name)
    if latitude is not None:
        kwargs["default_latitude"] = float(latitude)
    if longitude is not None:
        kwargs["default_longitude"] = float(longitude)

    # With no place configured, the tool works out where it is. These
    # settings control that; they are passed here as well as in
    # register_services so both weather tools behave identically.
    if config.get("location_auto_detect") is False:
        kwargs["auto_detect_location"] = False
    if config.get("location_cache_hours"):
        kwargs["location_cache_hours"] = float(config.get("location_cache_hours"))
    if config.get("location_cache_path"):
        kwargs["location_cache_path"] = str(config.get("location_cache_path"))

    return WeatherTool(**kwargs)


class ApplicationBuilder:

    def build(self) -> Application:
        engine = Engine()

        container = ServiceContainer()

        config = engine.services.get("config")

        register_services(container, config=config)

        register_modules(
            engine=engine,
            container=container,
        )

        conversation = ConversationManager(
            history=container.get("history"),
            brain=container.get("brain"),
            perception=container.get("perception"),
            context=container.get("context"),
            recall=container.get("recall"),
            store=container.get("store"),
            intent=container.get("intent"),
            planner=container.get("planner"),
            reasoning=container.get("reasoning"),
            router=container.get("router"),
            execution=container.get("execution"),
            monitor=container.get("monitor"),
            reflection=container.get("reflection"),
            permissions=container.get("permissions"),
            memory=container.get("memory"),
        )

        briefing = MorningBriefing(
            readings_provider=_build_weather_tool(config).current_readings,
            state_path=str(
                config.get("morning_briefing_state_path")
                or "data/morning_briefing.json"
            ),
            start_hour=int(config.get("morning_briefing_start_hour") or 6),
            end_hour=int(config.get("morning_briefing_end_hour") or 10),
            enabled=config.get("morning_briefing_enabled") is not False,
        )

        engine.start()

        # Built after engine.start() on purpose: the hologram overlay
        # creates the process's single QApplication during startup, and
        # the coding window has to adopt that instance rather than
        # trying to make its own.
        coding_enabled = config.get("coding_enabled") is not False

        coding_window = CodingWindowService(enabled=coding_enabled)

        coding_window.initialize()

        coding = CodingMode(
            workspace=container.get("workspace_manager").get_workspace("coding"),
            window=coding_window,
            enabled=coding_enabled,
            root=config.get("coding_workspace_root") or DEFAULT_WORKSPACE_ROOT,
        )

        logger.info(
            "Coding mode is %s (projects in %s).",
            "enabled" if coding_enabled else "disabled (set coding_enabled=true in config/settings.json)",
            coding.root,
        )

        return Application(
            engine=engine,
            conversation=conversation,
            voice=container.get("voice"),
            proactive=container.get("proactive"),
            hologram=container.get("hologram"),
            briefing=briefing,
            coding_window=coding_window,
            coding=coding,
        )
