"""
Persistent repository for registered desktop applications.

The repository is responsible only for saving and loading
Application objects from disk.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.modules.tools.launcher.models import Application


class ApplicationRepository:
    """
    Stores applications inside a JSON file.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[Application]:
        """
        Load all applications from disk.
        """

        if not self.path.exists():
            return []

        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return [Application(**item) for item in data]

    def save(self, applications: list[Application]) -> None:
        """
        Save applications to disk.
        """

        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self.path.open("w", encoding="utf-8") as file:
            json.dump(
                [asdict(app) for app in applications],
                file,
                indent=4,
            )

    def exists(self) -> bool:
        """
        Check whether the repository file exists.
        """

        return self.path.exists()

    def clear(self) -> None:
        """
        Remove all applications.
        """

        self.save([])
