"""
Configuration Manager for EON.

Loads configuration files and provides a centralized API
for accessing application settings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.core.logger import get_logger

logger = get_logger("Config")


class ConfigManager:
    """Central configuration manager for EON."""

    CONFIG_DIR = Path("config")

    def __init__(self) -> None:
        # Loaded once, here, rather than by each module that needs a
        # secret — .env holds things like the Telegram bot token and
        # Slack webhook URL used by src/modules/integrations, kept out
        # of settings.json (plain JSON, versioned) entirely.
        # load_dotenv() is a no-op if .env doesn't exist, so this is
        # safe even for setups that don't use any of the integrations.
        load_dotenv()

        self._config = self._load_json("config.json")
        self._settings = self._load_json("settings.json")
        self._models = self._load_json("models.json")

        logger.info("Configuration loaded successfully.")

    def _load_json(self, filename: str) -> dict[str, Any]:
        """
        Load a JSON configuration file.

        Args:
            filename: Name of the JSON file.

        Returns:
            Parsed JSON dictionary.
        """

        file_path = self.CONFIG_DIR / filename

        if not file_path.exists():
            logger.error("Missing configuration file: %s", filename)
            raise FileNotFoundError(file_path)

        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def get(self, key: str) -> Any:
        """
        Search for a configuration value.

        Search order:
        1. config.json
        2. settings.json
        3. models.json
        """

        if key in self._config:
            return self._config[key]

        if key in self._settings:
            return self._settings[key]

        if key in self._models:
            return self._models[key]

        logger.warning("Unknown configuration key requested: %s", key)
        return None
