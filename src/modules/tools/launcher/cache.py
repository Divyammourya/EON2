"""
Application Registry Cache.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.modules.tools.launcher.models import Application
from src.modules.tools.launcher.registry import ApplicationRegistry


class ApplicationCache:

    def __init__(
        self,
        path: str = "data/cache/applications.json",
    ) -> None:

        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def save(
        self,
        registry: ApplicationRegistry,
    ) -> None:

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = []

        for app in registry.list():
            data.append(
                {
                    "name": app.name,
                    "path": app.path,
                    "aliases": app.aliases,
                }
            )

        self.path.write_text(
            json.dumps(data, indent=4),
            encoding="utf-8",
        )

    def load(self) -> ApplicationRegistry:

        registry = ApplicationRegistry()

        if not self.exists():
            return registry

        data = json.loads(
            self.path.read_text(
                encoding="utf-8",
            )
        )

        for item in data:

            registry.register(
                Application(
                    name=item["name"],
                    path=item["path"],
                    aliases=item.get("aliases", []),
                )
            )

        return registry
