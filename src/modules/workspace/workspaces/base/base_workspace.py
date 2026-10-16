from __future__ import annotations

from src.modules.intent.models import Intent
from src.modules.workspace.models import WorkspaceSession
from src.modules.workspace.workspace import Workspace


class BaseWorkspace(Workspace):
    """
    Default implementation shared by all concrete workspaces.
    """

    def initialize(self) -> None:
        self._state.initialized = True

    def shutdown(self) -> None:
        self._state.initialized = False

    def open(self) -> None:
        self._state.is_open = True

    def close(self) -> None:
        self._state.is_open = False

    def activate(self) -> None:
        self._state.is_active = True

    def deactivate(self) -> None:
        self._state.is_active = False

    def save_session(self) -> WorkspaceSession:
        self._session = WorkspaceSession()
        return self._session

    def restore_session(self, session: WorkspaceSession) -> None:
        self._session = session

    def get_state(self):
        return self._state

    def get_metadata(self):
        return self._metadata

    def can_handle(self, intent: Intent) -> bool:
        return False

    def handle_intent(self, intent: Intent):
        raise NotImplementedError(
            f"{self.__class__.__name__} cannot handle intents."
        )
