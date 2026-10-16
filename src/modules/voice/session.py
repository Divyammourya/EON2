"""
Voice Session Manager for EON.

Maintains all active VoiceSession objects.

Responsible only for session lifecycle management.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from src.modules.voice.exceptions import VoiceSessionError
from src.modules.voice.models import (
    VoiceConfig,
    VoiceSession,
    VoiceState,
)


class VoiceSessionManager:
    """
    Manages all active voice sessions.
    """

    def __init__(self) -> None:
        self._sessions: dict[UUID, VoiceSession] = {}

    def create_session(
        self,
        config: VoiceConfig,
    ) -> VoiceSession:
        """
        Create and register a new session.
        """

        session = VoiceSession(config=config)

        self._sessions[session.session_id] = session

        return session

    def get_session(
        self,
        session_id: UUID,
    ) -> VoiceSession:
        """
        Return a session.

        Raises:
            VoiceSessionError
        """

        try:
            return self._sessions[session_id]

        except KeyError as exc:
            raise VoiceSessionError(
                f"Unknown voice session: {session_id}",
                session_id=str(session_id),
            ) from exc

    def remove_session(
        self,
        session_id: UUID,
    ) -> None:
        """
        Remove a session.
        """

        if session_id not in self._sessions:
            raise VoiceSessionError(
                f"Unknown voice session: {session_id}",
                session_id=str(session_id),
            )

        del self._sessions[session_id]

    def has_session(
        self,
        session_id: UUID,
    ) -> bool:
        """
        Return whether the session exists.
        """

        return session_id in self._sessions

    def get_sessions(self) -> list[VoiceSession]:
        """
        Return every active session.
        """

        return list(self._sessions.values())

    def session_count(self) -> int:
        """
        Return the number of active sessions.
        """

        return len(self._sessions)

    def clear(self) -> None:
        """
        Remove every active session.
        """

        self._sessions.clear()

    def update_session_state(
        self,
        session_id: UUID,
        state: VoiceState,
    ) -> VoiceSession:
        """
        Update a session state.
        """

        session = self.get_session(session_id)

        session.state = state
        session.updated_at = datetime.now(timezone.utc)

        return session

    def touch(
        self,
        session_id: UUID,
    ) -> None:
        """
        Update only the session timestamp.
        """

        session = self.get_session(session_id)

        session.updated_at = datetime.now(timezone.utc)
