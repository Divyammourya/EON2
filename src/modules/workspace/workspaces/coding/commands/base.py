from __future__ import annotations

from abc import ABC, abstractmethod


class CodingCommand(ABC):
    """
    Base class for every Coding Workspace command.
    """

    @abstractmethod
    def execute(self):
        """
        Execute the command.
        """
        raise NotImplementedError
