"""
Reasoner.
"""

from __future__ import annotations

import shlex

from src.modules.actions.models import ActionType
from src.modules.planner.models import Plan
from src.modules.reasoning.models import ReasoningResult

# Mirrors TerminalTool's blocklist as a defense-in-depth check at the
# reasoning layer, before a risky step is even handed to Execution.
_BLOCKED_COMMANDS = {
    "rm",
    "del",
    "format",
    "rd",
    "rmdir",
    "shutdown",
    "diskpart",
    "mkfs",
}


class Reasoner:
    """
    Determines whether a plan should execute.
    """

    def reason(
        self,
        plan: Plan,
    ) -> ReasoningResult:
        """
        Evaluate a plan before execution.

        Every step is checked individually. Any step that is judged
        unsafe causes the whole plan to be rejected — EON should not
        partially execute a plan it has doubts about.
        """

        for step in plan.steps:

            action = step.action

            if action.type == ActionType.RUN_COMMAND:

                blocked = self._blocked_command(action.target)

                if blocked is not None:
                    return ReasoningResult(
                        plan=plan,
                        approved=False,
                        message=(
                            f"I won't run '{blocked}' automatically — "
                            "it's a destructive command. Run it "
                            "manually if you're sure."
                        ),
                    )

        return ReasoningResult(
            plan=plan,
            approved=True,
            message="Plan approved.",
        )

    def _blocked_command(self, command: str) -> str | None:
        """
        Return the offending program name if the command is blocked,
        otherwise None.
        """

        try:
            parts = shlex.split(command, posix=False)
        except ValueError:
            # Unbalanced quotes etc. — treat as unsafe to be cautious.
            return command

        if not parts:
            return None

        program = parts[0].lower()

        if program in _BLOCKED_COMMANDS:
            return parts[0]

        return None
