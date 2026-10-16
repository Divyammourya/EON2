"""
EON Logging System

Provides a centralized logging configuration for the entire application.
Every module should obtain its logger using get_logger().
"""

from __future__ import annotations

import logging
from pathlib import Path

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

LOG_DIRECTORY = Path("logs")
LOG_FILE = LOG_DIRECTORY / "eon.log"

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------------------
# Internal Setup
# ---------------------------------------------------------------------

def _configure_logging() -> None:
    """Configure the global logging system."""

    LOG_DIRECTORY.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


_configure_logging()


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def get_logger(module_name: str) -> logging.Logger:
    """
    Return a logger for a specific EON module.

    Parameters
    ----------
    module_name : str
        Name of the module requesting the logger.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """

    return logging.getLogger(f"EON.{module_name}")
