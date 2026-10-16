from __future__ import annotations

from src.modules.intent.models import Intent, IntentType
from src.modules.workspace.workspaces.base.base_workspace import BaseWorkspace


class ChatWorkspace(BaseWorkspace):
    """
    Workspace responsible for normal conversational interaction.
    """

    def __init__(self) -> None:
        super().__init__()

        self._metadata.id = "chat"
        self._metadata.name = "Chat Workspace"
        self._metadata.description = "General conversation workspace."
        self._metadata.icon = "💬"
        self._metadata.category = "conversation"

    def can_handle(self, intent: Intent) -> bool:
        return intent.type == IntentType.CHAT

    def handle_intent(self, intent: Intent):
        """
        Handle a conversational intent.

        Actual LLM integration will be added later.
        """
        return {
            "workspace": self._metadata.id,
            "intent": intent.type.value,
            "message": intent.target,
        }
