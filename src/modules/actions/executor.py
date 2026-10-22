"""
Action Executor.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from src.modules.actions.models import (
    Action,
    ActionType,
    ActionResult,
)
from src.modules.tools.registry import ToolRegistry
from src.modules.tools.resource.service import ResourceService
from src.modules.vision.manager import VisionManager

# Action types that reach outside the conversation itself — launching
# apps, running commands, opening URLs/searches. Gated by
# automation_enabled since these are the ones with real side effects on
# the user's machine; CHAT is never gated.
_AUTOMATED_ACTION_TYPES = {
    ActionType.OPEN_APP,
    ActionType.SEARCH_WEB,
    ActionType.OPEN_URL,
    ActionType.RUN_COMMAND,
    ActionType.CLIPBOARD_READ,
    ActionType.CLIPBOARD_WRITE,
    ActionType.VOLUME_CONTROL,
    ActionType.BRIGHTNESS_CONTROL,
    ActionType.WINDOW_CONTROL,
    ActionType.TAKE_SCREENSHOT,
    ActionType.ORGANIZE_FILES,
    ActionType.TYPE_TEXT,
    ActionType.UI_CLICK,
    ActionType.UI_TYPE,
    ActionType.UI_LIST_ELEMENTS,
    ActionType.CALENDAR_READ,
    ActionType.CALENDAR_CREATE,
    ActionType.EMAIL_READ,
    ActionType.EMAIL_SEND,
    ActionType.MESSAGE_SEND,
    ActionType.MUSIC,
}

_SEARCH_URL_TEMPLATE = "https://www.google.com/search?q={query}"

#: The ``accessibility`` tool speaks element names — "click Save" — not
#: the ``verb:`` prefix convention this executor uses for the positional
#: tool, so the element command is written out per action.
#:
#: ``UI_TYPE`` is absent deliberately: typing needs a field *and* a
#: value, which that convention cannot express, so it stays on the
#: positional tool until the element tool grows the same shape.
_ELEMENT_COMMANDS = {
    ActionType.UI_CLICK: "click {target}",
    ActionType.UI_LIST_ELEMENTS: "list ui elements",
}


class ActionExecutor:

    def __init__(
        self,
        resources: ResourceService,
        tools: ToolRegistry | None = None,
        vision: VisionManager | None = None,
        automation_enabled: bool = True,
    ) -> None:
        self.resources = resources
        self.tools = tools
        self._element_tool_instance = None
        self.vision = vision
        self.automation_enabled = automation_enabled

    def execute(
        self,
        action: Action,
    ) -> ActionResult | None:

        if (
            action.type in _AUTOMATED_ACTION_TYPES
            and not self.automation_enabled
        ):
            return ActionResult(
                success=False,
                message=(
                    "Automation is currently disabled, sir. I can talk "
                    "about it, but I won't open apps, run commands, or "
                    "browse on your behalf until you enable "
                    "'automation_enabled' in config/settings.json."
                ),
            )

        if action.type == ActionType.OPEN_APP:

            result = self.resources.open(
                action.target,
            )

            if result is None:
                return None

            return ActionResult(
                success=result.success,
                message=result.message,
            )

        if action.type == ActionType.SEARCH_WEB:

            if self.tools is None:
                return ActionResult(
                    success=False,
                    message="Browser tool is not available.",
                )

            browser = self.tools.get("browser")

            if browser is None:
                return ActionResult(
                    success=False,
                    message="Browser tool is not registered.",
                )

            query = action.target.strip()

            if not query:
                return ActionResult(
                    success=False,
                    message="I didn't catch what to search for.",
                )

            search_url = _SEARCH_URL_TEMPLATE.format(
                query=quote_plus(query),
            )

            result = browser.execute(search_url)

            return ActionResult(
                success=result.success,
                message=(
                    f"Searching the web for '{query}'."
                    if result.success
                    else result.message
                ),
            )

        if action.type == ActionType.OPEN_URL:

            if self.tools is None:
                return ActionResult(
                    success=False,
                    message="Browser tool is not available.",
                )

            browser = self.tools.get("browser")

            if browser is None:
                return ActionResult(
                    success=False,
                    message="Browser tool is not registered.",
                )

            result = browser.execute(action.target)

            return ActionResult(
                success=result.success,
                message=result.message,
            )

        if action.type == ActionType.VIEW_SCREEN:

            if self.vision is None:
                return ActionResult(
                    success=False,
                    message="Vision is not available.",
                )

            result = self.vision.describe_screen(action.target)

            return ActionResult(
                success=result.success,
                message=(
                    result.description
                    if result.success
                    else result.message
                ),
            )

        if action.type == ActionType.RUN_COMMAND:

            if self.tools is None:
                return ActionResult(
                    success=False,
                    message="Terminal tool is not available.",
                )

            terminal = self.tools.get("terminal")

            if terminal is None:
                return ActionResult(
                    success=False,
                    message="Terminal tool is not registered.",
                )

            result = terminal.execute(action.target)

            return ActionResult(
                success=result.success,
                message=result.message,
            )

        # Deeper system control (automation/): clipboard, volume,
        # brightness, window management, screenshots, file organizing,
        # and typing/pasting text. All share the same dispatch shape,
        # so they're routed through one small helper instead of
        # repeating the tools-None/tool-missing checks per action type.
        if action.type == ActionType.CLIPBOARD_READ:
            return self._run_tool("clipboard", "", "Clipboard tool is not available.")

        if action.type == ActionType.CLIPBOARD_WRITE:
            return self._run_tool(
                "clipboard", action.target, "Clipboard tool is not available."
            )

        if action.type == ActionType.VOLUME_CONTROL:
            return self._run_tool(
                "volume", action.target, "Volume tool is not available."
            )

        if action.type == ActionType.BRIGHTNESS_CONTROL:
            return self._run_tool(
                "brightness", action.target, "Brightness tool is not available."
            )

        if action.type == ActionType.WINDOW_CONTROL:
            return self._run_tool(
                "window", action.target, "Window tool is not available."
            )

        if action.type == ActionType.TAKE_SCREENSHOT:
            return self._run_tool(
                "screenshot", action.target, "Screenshot tool is not available."
            )

        if action.type == ActionType.ORGANIZE_FILES:
            return self._run_tool(
                "file_organizer",
                action.target,
                "File organizer tool is not available.",
            )

        if action.type == ActionType.TYPE_TEXT:
            return self._run_tool(
                "type_text", action.target, "Type text tool is not available."
            )

        # Precise UI control via Accessibility APIs (automation/). One
        # UIControlTool instance handles all three operations, told
        # apart by a prefix — same convention as CALENDAR_READ/CREATE
        # and EMAIL_READ/SEND below.
        if action.type == ActionType.UI_CLICK:
            return self._run_ui_action(
                ActionType.UI_CLICK,
                action.target,
                f"click:{action.target}",
                "UI control tool is not available.",
            )

        if action.type == ActionType.UI_TYPE:
            return self._run_tool(
                "ui_control",
                f"type:{action.target}",
                "UI control tool is not available.",
            )

        if action.type == ActionType.UI_LIST_ELEMENTS:
            return self._run_ui_action(
                ActionType.UI_LIST_ELEMENTS,
                action.target,
                "list:",
                "UI control tool is not available.",
            )

        # Calendar / Email / Messaging (integrations/). Read/create
        # and read/send are split into separate ActionTypes (unlike
        # e.g. VOLUME_CONTROL, which bundles up/down/mute into one)
        # specifically so the permissions layer can auto-approve reads
        # while still requiring confirmation for anything that puts
        # content in front of another person. The prefix here is how
        # each single Tool instance tells which operation was asked
        # for — see CalendarTool/EmailTool.execute().
        if action.type == ActionType.CALENDAR_READ:
            return self._run_tool(
                "calendar", f"read:{action.target}", "Calendar tool is not available."
            )

        if action.type == ActionType.CALENDAR_CREATE:
            return self._run_tool(
                "calendar",
                f"create:{action.target}",
                "Calendar tool is not available.",
            )

        if action.type == ActionType.EMAIL_READ:
            return self._run_tool(
                "email", f"read:{action.target}", "Email tool is not available."
            )

        if action.type == ActionType.EMAIL_SEND:
            return self._run_tool(
                "email", f"send:{action.target}", "Email tool is not available."
            )

        if action.type == ActionType.MESSAGE_SEND:
            return self._run_tool(
                "messaging", action.target, "Messaging tool is not available."
            )

        if action.type == ActionType.WEATHER:
            # Deliberately NOT gated by automation_enabled (unlike the
            # other automation actions above): it's read-only, public
            # information with no privacy or destructive dimension —
            # closer to a chat answer than to clipboard/calendar/email
            # access, which do carry a real privacy angle.
            return self._run_tool(
                "weather", action.target, "Weather tool is not available."
            )

        if action.type == ActionType.MUSIC:
            return self._run_tool(
                "music", action.target, "Music tool is not available."
            )

        return None

    def _run_ui_action(
        self,
        action_type: ActionType,
        target: str,
        fallback_target: str,
        missing_message: str,
    ) -> ActionResult:
        """Runs a UI action, preferring element targeting over position.

        ``accessibility`` finds an element by its accessible name, so
        "click the Save button" survives a window being moved or
        resized. ``ui_control`` drives the same operations positionally,
        which does not. So the element tool is tried first and the
        positional one is the fallback — which is also what happens on a
        machine where UI Automation is unavailable, and on anything that
        is not Windows.

        Args:
            action_type: Which UI action this is.
            target: The element name to act on.
            fallback_target: The positional tool's command, unchanged.
            missing_message: Reported when neither tool can run.

        Returns:
            The first successful result, or the fallback's.
        """
        element_command = _ELEMENT_COMMANDS.get(action_type)
        element_tool = self._element_tool()

        if element_command is not None and element_tool is not None:
            result = element_tool.execute(
                element_command.format(target=target)
            )

            if result.success:
                return ActionResult(
                    success=True, message=result.message
                )

        return self._run_tool("ui_control", fallback_target, missing_message)

    def _element_tool(self):
        """The element-based UI tool, built on first use.

        It is not in the shared tool registry, so the executor builds it
        here rather than never using it. Lazily, because it is only
        useful on Windows and constructing it costs a UI Automation
        lookup, and defensively, because the import must not break a
        machine that has no UI Automation at all.
        """
        if self._element_tool_instance is not None:
            return self._element_tool_instance

        if self.tools is not None:
            registered = self.tools.get("accessibility")

            if registered is not None:
                self._element_tool_instance = registered
                return registered

        try:
            from src.modules.automation.accessibility import AccessibilityTool

            self._element_tool_instance = AccessibilityTool()
        except Exception:
            return None

        return self._element_tool_instance

    def _run_tool(
        self,
        tool_name: str,
        target: str,
        missing_message: str,
    ) -> ActionResult:
        """Runs a registered tool by name and wraps its result.

        Shared by every automation action branch above, since they all
        follow the same shape: check the tool exists, run it with the
        action's target text, and wrap the ToolResult as an
        ActionResult.
        """
        if self.tools is None:
            return ActionResult(success=False, message=missing_message)

        tool = self.tools.get(tool_name)

        if tool is None:
            return ActionResult(success=False, message=missing_message)

        result = tool.execute(target)

        return ActionResult(success=result.success, message=result.message)
