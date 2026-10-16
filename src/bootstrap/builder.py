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

from src.modules.conversation.manager import ConversationManager


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

        engine.start()

        return Application(
            engine=engine,
            conversation=conversation,
            voice=container.get("voice"),
            proactive=container.get("proactive"),
            hologram=container.get("hologram"),
        )
