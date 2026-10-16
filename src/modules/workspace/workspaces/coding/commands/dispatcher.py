from __future__ import annotations


class CommandDispatcher:
    """
    Executes Coding Workspace commands.
    """

    def dispatch(
        self,
        command,
    ):
        return command.execute()
