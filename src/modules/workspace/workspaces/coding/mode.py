"""Coding mode: one window, one project, one boundary.

Typing ``coding`` opens EON's coding window and puts the console into
this mode. From then on, every line typed goes to the coding workspace
rather than to the chat brain, and EON writes files inside the current
project only.

    You: coding calculator
    EON: Coding window open. Project 'calculator' in
         C:\\Users\\divya\\Desktop\\EON_workspace\\calculator
    You: create file src/main.py
    EON: Wrote src/main.py (0 bytes).
    You: run command python src/main.py
    EON: I'd like to run: python src/main.py  — shall I? (yes/no)

Design notes:
    - **Commands are gated, writes are not.** You asked for exactly
      this, and it's the right split: writing a file inside the project
      is reversible and visible in the window, while running a command
      is neither. So a write just happens and is reported; anything
      that would *execute* stops and asks first, every time.
    - The gate is deliberately in this mode rather than delegated to
      the permissions layer. The coding workspace is called directly,
      not through the action pipeline, so the permissions layer never
      sees these commands — if the gate isn't here, there isn't one.
    - Failures are reported as failures. A plan that reports success
      for a step that did nothing would make EON say it wrote your code
      when it hadn't, so the workspace's executor was fixed to stop at
      the first failed step and say why.

Requires: Python 3.12+ (no extra packages)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.logger import get_logger
from src.modules.intent.models import Intent, IntentType
from src.modules.workspace.workspaces.coding.session import (
    DEFAULT_WORKSPACE_ROOT,
    CodingSession,
    CodingSessionError,
    list_projects,
    sanitise_project_name,
)
from src.modules.workspace.workspaces.coding.window_queries import WindowQueries

logger = get_logger("CodingMode")

# Typed on its own to enter the mode.
ENTER_WORDS = frozenset(
    {
        "coding",
        "code",
        "coding mode",
        "coding workspace",
        "the coding workspace",
        "code mode",
        "code workspace",
        "start coding",
        "lets code",
        "let's code",
    }
)

# Typed to leave it.
LEAVE_WORDS = frozenset(
    {"done", "exit coding", "stop coding", "quit coding", "close coding", "bye coding"}
)

# Yes/no, for confirming a command.
_YES = frozenset({"y", "yes", "yeah", "yep", "ok", "okay", "sure", "do it", "go ahead", "haan", "ha"})
_NO = frozenset({"n", "no", "nope", "cancel", "stop", "don't", "dont", "nahi", "na"})


@dataclass(slots=True)
class CodingRequest:
    """A line that asks to enter coding mode, and for which project."""

    project: str


def parse_coding_request(text: str) -> CodingRequest | None:
    """Whether a line asks to start coding, and for which project.

    Accepts ``coding``, ``coding calculator``, and the same with
    ``start``/``let's`` in front.

    Args:
        text: The line the user typed.

    Returns:
        The request, or ``None`` if this isn't a coding request.
    """
    stripped = text.strip()

    if not stripped:
        return None

    lowered = stripped.lower()

    # "open coding workspace" is how someone naturally asks for this,
    # and without stripping the "open" it fell through to the brain,
    # which read "workspace" as an application to launch.
    for prefix in ("open ", "start ", "let's ", "lets ", "let us "):
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix):].strip()
            stripped = stripped[len(prefix):].strip()
            break

    if lowered in ENTER_WORDS:
        return CodingRequest(project="")

    if lowered.startswith("coding "):
        return CodingRequest(project=stripped[len("coding "):].strip())

    return None


def is_leave_request(text: str) -> bool:
    """Whether a line asks to leave coding mode."""
    return text.strip().lower() in LEAVE_WORDS


class CodingMode:
    """Dispatches typed lines to the coding workspace.

    Attributes:
        active: Whether the mode is on.
        session: The current project, if one is open.
        pending_command: A command waiting for a yes/no, if any.
    """

    def __init__(
        self,
        *,
        workspace,
        window=None,
        enabled: bool = True,
        root: str | Path = DEFAULT_WORKSPACE_ROOT,
    ) -> None:
        """Builds the mode.

        Args:
            workspace: The coding workspace to dispatch to. Anything
                exposing ``handle_intent`` and ``parser`` will do,
                which is what lets the tests drive a stub.
            window: Optional coding window, refreshed after each change.
            enabled: Whether coding mode can be entered at all.
            root: The workspace root projects live under.
        """
        self._workspace = workspace
        self._window = window
        self._enabled = enabled
        self._root = root

        self._session: CodingSession | None = None
        self._pending: str | None = None
        self._last_project: str = ""

    # --- state ------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def active(self) -> bool:
        return self._session is not None

    @property
    def session(self) -> CodingSession | None:
        return self._session

    @property
    def pending_command(self) -> str | None:
        return self._pending

    @property
    def root(self) -> Path:
        return Path(self._root).expanduser()

    # --- entering and leaving --------------------------------------------

    def enter(self, project: str = "") -> str:
        """Starts a coding session and opens the window.

        Args:
            project: The project to create or resume. Empty means
                "resume whatever was last used", falling back to
                listing what exists.

        Returns:
            What to say to the user.
        """
        if not self._enabled:
            return (
                "Coding mode is switched off. Set coding_enabled=true in "
                "config/settings.json to turn it on."
            )

        name = project or self._last_project

        if not name:
            existing = list_projects(self._root)

            if len(existing) == 1:
                name = existing[0]
            elif existing:
                return (
                    "Which project? You have: "
                    + ", ".join(existing)
                    + ". Say 'coding <name>' to open one."
                )
            else:
                return (
                    f"No projects yet in {self.root}. Say 'coding "
                    "<name>' to start one — for example 'coding calculator'."
                )

        try:
            self._session = CodingSession(root=self._root, name=name)
        except CodingSessionError as error:
            return str(error)

        self._last_project = self._session.name
        self._pending = None

        self._open_project_in_workspace()
        self._bind_window_queries()
        self._show_window()

        return (
            f"Coding window open. Project '{self._session.name}' in "
            f"{self._session.project_root_display}\n"
            "    create file <path>   create directory <path>   read file <path>\n"
            "    run command <cmd>    project <name>           done"
        )

    def leave(self) -> str:
        """Ends the session and closes the window."""
        if self._session is None:
            return "You're not in coding mode."

        name = self._session.name

        self._session = None
        self._pending = None

        if self._window is not None:
            try:
                self._window.close_window()
            except Exception as error:  # pragma: no cover - UI safety net
                logger.warning("Could not close the coding window: %s", error)

        return f"Left coding mode. '{name}' is saved."

    # --- handling a line --------------------------------------------------

    def handle(self, line: str) -> str:
        """Handles one line typed while in coding mode.

        Args:
            line: What the user typed.

        Returns:
            What to say back.
        """
        text = line.strip()

        if not text:
            return ""

        if is_leave_request(text):
            return self.leave()

        # A command waiting on a yes/no comes first: anything else
        # typed while a confirmation is open would otherwise be read as
        # a fresh command, and a stray "yes" later could run it.
        if self._pending is not None:
            return self._resolve_pending(text)

        mode_reply = self._handle_mode_command(text)

        if mode_reply is not None:
            return mode_reply

        return self._dispatch(text)

    def _handle_mode_command(self, text: str) -> str | None:
        """Handles the commands that belong to the mode, not the workspace.

        Returns ``None`` when the line is a coding command, so it falls
        through to the workspace.
        """
        lowered = text.lower()

        if lowered in {"projects", "list projects"}:
            existing = list_projects(self._root)

            if not existing:
                return f"No projects yet in {self.root}."

            return "Projects: " + ", ".join(existing)

        for prefix in ("project ", "new project ", "switch to "):
            if lowered.startswith(prefix):
                name = text[len(prefix):].strip()
                return self._switch_project(name)

        return None

    def _switch_project(self, name: str) -> str:
        """Creates or resumes a project by name."""
        try:
            self._session = CodingSession(root=self._root, name=name)
        except CodingSessionError as error:
            return str(error)

        self._last_project = self._session.name
        self._open_project_in_workspace()
        self._bind_window_queries()
        self._show_window()

        return f"Now in '{self._session.name}' ({self._session.project_root_display})."

    def _open_project_in_workspace(self) -> None:
        """Tells the coding workspace which folder it is working in."""
        assert self._session is not None

        try:
            self._workspace.handle_intent(
                Intent(
                    IntentType.FILE,
                    target=f"open project {self._session.project_root}",
                )
            )
        except Exception as error:
            logger.warning("Could not open the project in the workspace: %s", error)

    def _dispatch(self, text: str) -> str:
        """Sends a coding command to the workspace."""
        if self._session is None:
            return "You're not in a project yet."

        action = self._parsed_action(text)

        if action == "run_command":
            command = self._parsed_argument(text, "command") or text
            self._pending = command
            return f"I'd like to run: {command}  — shall I? (yes/no)"

        try:
            result = self._workspace.handle_intent(
                Intent(IntentType.FILE, target=text)
            )
        except Exception as error:
            logger.warning("Coding command failed: %s", error)
            return f"That didn't work: {error}"

        self._refresh_window()

        return self._describe(result)

    def _resolve_pending(self, text: str) -> str:
        """Acts on a yes/no for a command that was waiting."""
        answer = text.strip().lower()
        command = self._pending or ""
        self._pending = None

        if answer in _NO:
            return f"Fine — I won't run `{command}`."

        if answer not in _YES:
            # Anything that isn't a clear yes is treated as "not yet",
            # rather than guessing — and the command stays available.
            self._pending = command
            return "Just to be sure — yes or no?"

        try:
            result = self._workspace.handle_intent(
                Intent(IntentType.SYSTEM, target=f"run command {command}")
            )
        except Exception as error:
            logger.warning("Command failed: %s", error)
            return f"That command failed: {error}"

        self._refresh_window()

        return self._describe(result)

    # --- reading the workspace -------------------------------------------

    def _parsed_action(self, text: str) -> str | None:
        """The action the workspace's parser sees in ``text``, if any."""
        parser = getattr(self._workspace, "parser", None)

        if parser is None:
            return None

        try:
            parsed = parser.parse(text)
        except Exception:
            return None

        return getattr(parsed, "action", None)

    def _parsed_argument(self, text: str, key: str) -> str | None:
        """One argument the workspace's parser pulled out of ``text``."""
        parser = getattr(self._workspace, "parser", None)

        if parser is None:
            return None

        try:
            parsed = parser.parse(text)
        except Exception:
            return None

        arguments = getattr(parsed, "arguments", None) or {}

        return arguments.get(key)

    @staticmethod
    def _describe(result) -> str:
        """Turns a workspace result into something worth reading.

        Handles both shapes the workspace returns: a ``PlanResult`` for
        planned commands, and a plain dict for the AI-driven ones.
        """
        if result is None:
            return "Done."

        if isinstance(result, dict):
            if result.get("success") is False:
                return f"That didn't work: {result.get('error', 'unknown error')}"

            for value in result.values():
                if isinstance(value, dict) and value.get("path"):
                    return f"Done: {value['path']}"

            return "Done."

        success = getattr(result, "success", None)
        message = getattr(result, "message", "")

        if success is False:
            return f"That didn't work: {message}"

        # Prefer naming the file that was written over the generic
        # "Plan executed successfully." — you want to see what changed.
        context = getattr(result, "context", None)
        data = getattr(context, "data", None) or {}

        for value in data.values():
            if isinstance(value, dict) and value.get("path"):
                written = value["path"]
                size = value.get("bytes_written")
                if size is not None:
                    return f"Wrote {written} ({size} bytes)."
                return f"Done: {written}"

        return message or "Done."

    # --- the window -------------------------------------------------------

    def _bind_window_queries(self) -> None:
        """Points the window's sidebar at this workspace.

        The Search, Outline and Git sections are backed by the
        workspace's own managers, which EON already had — they were
        only reachable from the console. Binding them here, where the
        workspace is, keeps ``window.py`` free of any knowledge of the
        workspace at all: the window asks questions, this answers them.

        Called before the window is shown, so the very first refresh
        already has something to ask.
        """
        if self._window is None:
            return

        bind = getattr(self._window, "bind_queries", None)

        if bind is None:
            return

        try:
            bind(WindowQueries(self._workspace))
        except Exception as error:  # pragma: no cover - UI safety net
            logger.warning("Could not bind the window's sidebar: %s", error)

    def _show_window(self) -> None:
        """Opens the window on the current project."""
        if self._window is None or self._session is None:
            return

        try:
            self._window.show_project(
                project_root=self._session.project_root,
                title=self._session.name,
            )
        except Exception as error:  # pragma: no cover - UI safety net
            logger.warning("Could not open the coding window: %s", error)

    def _refresh_window(self) -> None:
        """Tells the window the files changed."""
        if self._window is None:
            return

        try:
            self._window.refresh()
        except Exception as error:  # pragma: no cover - UI safety net
            logger.warning("Could not refresh the coding window: %s", error)
