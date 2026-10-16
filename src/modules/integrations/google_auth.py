"""
Google Auth Manager.

Shared OAuth handling for Calendar + Gmail — both are Google APIs
using the same "installed app" OAuth flow and (for EON's purposes) the
same Google account, so there's one client secret and one cached token
covering both, rather than each tool doing its own auth dance.

Setup (one-time, per user):
    1. In Google Cloud Console, create a project, enable the "Google
       Calendar API" and "Gmail API", and create an OAuth Client ID of
       type "Desktop app".
    2. Download the client secret JSON and save it at
       config/google_credentials.json (or wherever
       GOOGLE_CREDENTIALS_PATH in .env points).
    3. The first time a calendar/email action actually runs, a browser
       window opens asking you to sign in and consent. After that, the
       token is cached at data/google_token.json and refreshed
       automatically — no browser popup on subsequent runs.
"""

from __future__ import annotations

from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("Integrations.GoogleAuth")

# Both Calendar and Gmail scopes are requested together up front. If
# only Calendar scopes were requested first and Gmail scopes were
# added later, the cached token wouldn't cover them and the user would
# be silently asked to re-consent — simpler to ask for everything EON
# might need once, the first time either tool is used.
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


class GoogleAuthError(Exception):
    """Raised when Google credentials can't be obtained (missing
    client secret, consent declined, etc.) — callers turn this into a
    ToolResult rather than letting it propagate."""


class GoogleAuthManager:
    """
    Loads/refreshes/creates the Google OAuth credentials shared by the
    Calendar and Email tools.
    """

    def __init__(
        self,
        credentials_path: str,
        token_path: str,
    ) -> None:
        self._credentials_path = Path(credentials_path)
        self._token_path = Path(token_path)
        self._credentials = None  # cached across calls in this process

    def has_cached_credentials(self) -> bool:
        """Return whether Google auth can likely proceed without opening consent."""

        return self._credentials is not None or self._token_path.exists()

    def get_credentials(self):
        """
        Returns valid ``google.oauth2.credentials.Credentials``,
        refreshing or running the interactive consent flow as needed.

        Raises ``GoogleAuthError`` (with a message safe to show the
        user) if that isn't possible — e.g. the client secret file is
        missing, or the required packages aren't installed.
        """

        if self._credentials is not None and self._credentials.valid:
            return self._credentials

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as error:
            raise GoogleAuthError(
                "Google API packages aren't installed. Run: pip install "
                "google-api-python-client google-auth-httplib2 "
                f"google-auth-oauthlib. ({error})"
            ) from error

        creds = None

        if self._token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(self._token_path), SCOPES
                )
            except Exception:
                logger.exception(
                    "Couldn't read the cached Google token at %s — "
                    "will re-authenticate.",
                    self._token_path,
                )
                creds = None

        if creds and creds.valid:
            self._credentials = creds
            return creds

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_token(creds)
                self._credentials = creds
                return creds
            except Exception:
                logger.exception(
                    "Google token refresh failed — will re-authenticate."
                )
                creds = None

        if not self._credentials_path.exists():
            raise GoogleAuthError(
                f"No Google client secret found at "
                f"'{self._credentials_path}'. Download one from Google "
                f"Cloud Console (OAuth Client ID, type 'Desktop app') "
                f"and save it there, or point GOOGLE_CREDENTIALS_PATH "
                f"in .env at it."
            )

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self._credentials_path), SCOPES
            )
            # Opens a browser for the user to sign in/consent. Only
            # happens once (or after a token is revoked/expires with
            # no refresh token) — subsequent calls use the cached
            # token above.
            creds = flow.run_local_server(port=0)
        except Exception as error:
            raise GoogleAuthError(
                f"Google sign-in didn't complete: {error}"
            ) from error

        self._save_token(creds)
        self._credentials = creds
        return creds

    def _save_token(self, creds) -> None:
        try:
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_path.write_text(creds.to_json())
        except Exception:
            logger.exception(
                "Couldn't cache the Google token at %s — you'll be "
                "asked to sign in again next time.",
                self._token_path,
            )
