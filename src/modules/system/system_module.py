"""
System Module
"""

from src.core.logger import get_logger
from src.interfaces.module import Module

logger = get_logger("System")


class SystemModule(Module):

    @property
    def name(self) -> str:
        return "System"

    def initialize(self) -> None:
        logger.info("System initialized.")

    def start(self) -> None:
        logger.info("System started.")

    def stop(self) -> None:
        logger.info("System stopped.")

    def shutdown(self) -> None:
        logger.info("System shutdown.")

    def health_check(self) -> bool:
        return True
