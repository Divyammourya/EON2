"""
UI Control Tool.

Interacts with actual on-screen UI elements — buttons, links,
checkboxes, text fields, menu items — via Windows' UI Automation (UIA)
API, using the `pywinauto` wrapper. This is deliberately different
from clicking at screen coordinates guessed from a screenshot: UIA
enumerates the real element tree of the foreground window by name and
role (the same mechanism screen readers use), so a click lands on the
right control by name even if the window has moved, been resized, or
the screen resolution has changed.

Requires the `pywinauto` package (see requirements.txt).
"""

from __future__ import annotations

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

_MAX_ELEMENTS_LISTED = 25

# Control types worth checking first for a "click" request — anything
# actually invokable/selectable. Falls back to searching every control
# type if nothing matches here, in case it's an unusual custom control.
_CLICKABLE_CONTROL_TYPES = (
    "Button",
    "CheckBox",
    "RadioButton",
    "Hyperlink",
    "MenuItem",
    "TabItem",
    "ListItem",
    "TreeItem",
)

# Control types worth checking first for a "type into" request.
_TEXT_ENTRY_CONTROL_TYPES = (
    "Edit",
    "Document",
    "ComboBox",
)

_NOT_AVAILABLE_MESSAGE = (
    "UI control requires the 'pywinauto' package (pip install pywinauto). Error: {error}"
)


class UIControlTool(Tool):
    """Tool to click and type into named UI elements via UI Automation."""

    @property
    def name(self) -> str:
        return "ui_control"

    def _active_window(self):
        """Returns a pywinauto UIA wrapper for the foreground window."""
        import win32gui
        from pywinauto import Desktop

        hwnd = win32gui.GetForegroundWindow()
        desktop = Desktop(backend="uia")

        return desktop.window(handle=hwnd)

    def _find_control(
        self,
        window,
        name: str,
        control_types: tuple[str, ...] | None = None,
    ):
        """Finds the best-matching descendant control by visible name.

        Tries an exact (case-insensitive) match first, then falls back
        to a substring match either direction, across the given
        control types (or every control type if none are given).
        """
        name_lower = name.strip().lower()

        if not name_lower:
            return None

        try:
            candidates = window.descendants()
        except Exception:
            return None

        if control_types:
            candidates = [
                control
                for control in candidates
                if getattr(control.element_info, "control_type", None) in control_types
            ]

        exact_matches = []
        partial_matches = []

        for control in candidates:
            try:
                title = (control.window_text() or "").strip().lower()
            except Exception:
                continue

            if not title:
                continue

            if title == name_lower:
                exact_matches.append(control)
            elif name_lower in title or title in name_lower:
                partial_matches.append(control)

        for group in (exact_matches, partial_matches):
            if group:
                return group[0]

        return None

    def click(self, target: str) -> ToolResult:
        """Finds a named clickable element in the foreground window and
        clicks it."""
        try:
            window = self._active_window()

            control = self._find_control(window, target, _CLICKABLE_CONTROL_TYPES)

            if control is None:
                # Not a standard clickable type — search everything
                # before giving up (e.g. a custom-drawn control).
                control = self._find_control(window, target)

            if control is None:
                return ToolResult(
                    success=False,
                    message=(
                        f"I couldn't find a control named '{target}' in the "
                        "active window."
                    ),
                )

            control.click_input()

            return ToolResult(success=True, message=f"Clicked '{target}'.")

        except Exception as error:
            return ToolResult(
                success=False, message=_NOT_AVAILABLE_MESSAGE.format(error=error)
            )

    def type_into(self, field_name: str, text: str) -> ToolResult:
        """Finds a named text-entry element in the foreground window
        and types ``text`` into it."""
        try:
            window = self._active_window()

            control = self._find_control(window, field_name, _TEXT_ENTRY_CONTROL_TYPES)

            if control is None:
                control = self._find_control(window, field_name)

            if control is None:
                return ToolResult(
                    success=False,
                    message=(
                        f"I couldn't find a field named '{field_name}' in the "
                        "active window."
                    ),
                )

            control.set_focus()

            try:
                # Most standard text/edit controls support the Value
                # pattern, which sets the whole value in one call.
                control.set_text(text)
            except Exception:
                # Some custom-drawn fields don't implement the Value
                # pattern — fall back to simulated keystrokes.
                control.type_keys(text, with_spaces=True)

            return ToolResult(
                success=True, message=f"Typed '{text}' into '{field_name}'."
            )

        except Exception as error:
            return ToolResult(
                success=False, message=_NOT_AVAILABLE_MESSAGE.format(error=error)
            )

    def list_elements(self) -> ToolResult:
        """Lists named, interactable elements in the foreground window.

        Useful both as its own "what can I click?" command and as a
        way to sanity-check why a click/type request couldn't find
        something (e.g. the visible label doesn't match what UIA
        reports as the element's name).
        """
        try:
            window = self._active_window()
            candidates = window.descendants()

            named_elements = []

            for control in candidates:
                try:
                    title = (control.window_text() or "").strip()
                    control_type = control.element_info.control_type
                except Exception:
                    continue

                if title:
                    named_elements.append(f"{title} ({control_type})")

            if not named_elements:
                return ToolResult(
                    success=False,
                    message="I couldn't find any named elements in the active window.",
                )

            preview = named_elements[:_MAX_ELEMENTS_LISTED]
            summary = "; ".join(preview)

            remaining = len(named_elements) - len(preview)

            if remaining > 0:
                summary += f"; and {remaining} more"

            return ToolResult(success=True, message=summary)

        except Exception as error:
            return ToolResult(
                success=False, message=_NOT_AVAILABLE_MESSAGE.format(error=error)
            )

    def execute(self, command: str = "") -> ToolResult:
        """Dispatches based on the ``"click:"``/``"type:"``/``"list:"``
        prefix added by the action executor (mirrors the convention
        used by CalendarTool/EmailTool for their own sub-operations).

        For ``"type:"``, the remainder is ``"<field name>|<text>"``,
        as produced by the intent classifier's UI_TYPE detection.
        """
        text = (command or "").strip()

        if text.startswith("list:"):
            return self.list_elements()

        if text.startswith("type:"):
            remainder = text[len("type:") :].strip()
            field_name, _, value = remainder.partition("|")
            return self.type_into(field_name.strip(), value.strip())

        if text.startswith("click:"):
            return self.click(text[len("click:") :].strip())

        # Fallback for direct calls (e.g. tests) without a prefix.
        return self.click(text)
