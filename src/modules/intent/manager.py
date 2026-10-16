from __future__ import annotations

from typing import TYPE_CHECKING

from src.modules.intent.classifier import IntentClassifier
from src.modules.intent.models import Intent, IntentType
from src.modules.workspace.router import WorkspaceRouter

if TYPE_CHECKING:
    from src.modules.memory.service import MemoryService


class IntentManager:

    def __init__(
        self,
        memory: "MemoryService | None" = None,
        router: WorkspaceRouter | None = None,
    ) -> None:

        self.classifier = IntentClassifier()

        self._memory = memory

        self._router = router

    def detect(self, message: str) -> Intent:
        if self._memory is not None:
            learned = self._memory.get_learned_phrase(message)
            if learned is not None:
                intent_type_value, target = learned
                try:
                    return Intent(IntentType(intent_type_value), target=target)
                except ValueError:
                    # Stored value no longer matches a known IntentType
                    # (e.g. after an enum rename) — fall through to
                    # normal classification rather than erroring out.
                    pass

        return self.classifier.classify(message)

    def process(self, message: str):
        """
        Detect an intent and, if a workspace router has been provided,
        immediately dispatch it to the appropriate workspace.

        Returns either:

        • Intent
        • workspace result
        """

        intent = self.detect(message)

        if self._router is None:
            return intent

        return self._router.route(intent)
