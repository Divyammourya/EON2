"""
Accessibility / UI Automation Tool.

Provides precise Windows UI control through Microsoft UI Automation
instead of screenshot-coordinate guessing. It can list UI elements in
the active window, invoke controls by accessible name, focus elements,
and set text fields when the target app exposes the Value pattern.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

_TREE_SCOPE_CHILDREN = 0x2
_TREE_SCOPE_DESCENDANTS = 0x4
_TREE_SCOPE_SUBTREE = _TREE_SCOPE_CHILDREN | _TREE_SCOPE_DESCENDANTS

_UIA_INVOKE_PATTERN_ID = 10000
_UIA_SELECTION_ITEM_PATTERN_ID = 10010
_UIA_VALUE_PATTERN_ID = 10002
_UIA_TOGGLE_PATTERN_ID = 10015

_CONTROL_TYPES = {
    "button": 50000,
    "calendar": 50001,
    "checkbox": 50002,
    "combo box": 50003,
    "field": 50004,
    "edit": 50004,
    "text field": 50004,
    "hyperlink": 50005,
    "image": 50006,
    "list item": 50007,
    "list": 50008,
    "menu": 50009,
    "menu bar": 50010,
    "menu item": 50011,
    "progress bar": 50012,
    "radio button": 50013,
    "scroll bar": 50014,
    "slider": 50015,
    "spinner": 50016,
    "status bar": 50017,
    "tab": 50018,
    "tab item": 50019,
    "text": 50020,
    "tree": 50023,
    "tree item": 50024,
    "window": 50032,
}

_CONTROL_TYPE_NAMES = {value: key for key, value in _CONTROL_TYPES.items()}
_LIST_WORDS = ("list", "show", "what", "find")
_CLICK_WORDS = ("click", "press", "invoke", "select", "choose", "open")
_FOCUS_WORDS = ("focus", "go to", "place cursor in")
_SET_TEXT_PATTERN = re.compile(
    r"(?:type|enter|set|fill|write)\s+(?P<value>.+?)\s+(?:into|in|on)\s+(?P<target>.+)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class UIElementSummary:
    """Small, serializable description of a UIA element."""

    name: str
    control_type: str
    automation_id: str = ""
    class_name: str = ""


@dataclass(slots=True)
class UICommand:
    """Parsed accessibility command."""

    operation: str
    target: str = ""
    value: str = ""
    control_type: str = ""


class AccessibilityTool(Tool):
    """Precise UI control through Windows UI Automation."""

    @property
    def name(self) -> str:
        return "accessibility"

    def execute(self, command: str = "") -> ToolResult:
        parsed = self.parse_command(command)

        if parsed.operation == "unknown":
            return ToolResult(
                success=False,
                message=(
                    "I didn't understand that UI command. Try 'click the Submit "
                    "button', 'list buttons', or 'type hello into search field'."
                ),
            )

        try:
            root = self._active_window_element()

            if parsed.operation == "list":
                elements = self._find_elements(root, parsed.control_type)
                return self._format_elements(elements, parsed.control_type)

            element = self._find_best_match(
                root=root,
                target=parsed.target,
                control_type=parsed.control_type,
            )

            if element is None:
                return ToolResult(
                    success=False,
                    message=f"I couldn't find a UI element matching '{parsed.target}'.",
                )

            if parsed.operation == "set_text":
                return self._set_text(element, parsed.value, parsed.target)

            if parsed.operation == "focus":
                element.SetFocus()
                return ToolResult(success=True, message=f"Focused '{parsed.target}'.")

            return self._invoke(element, parsed.target)

        except Exception as error:
            return ToolResult(success=False, message=f"UI Automation failed: {error}")

    @staticmethod
    def parse_command(command: str) -> UICommand:
        text = " ".join((command or "").strip().split())
        lowered = text.lower()

        if not lowered:
            return UICommand(operation="unknown")

        set_match = _SET_TEXT_PATTERN.search(text)

        if set_match:
            return UICommand(
                operation="set_text",
                target=AccessibilityTool._clean_target(set_match.group("target")),
                value=set_match.group("value").strip().strip("'\""),
                control_type="field",
            )

        control_type = AccessibilityTool._detect_control_type(lowered)

        if any(lowered.startswith(word) for word in _LIST_WORDS) and (
            " ui" in lowered
            or " element" in lowered
            or " control" in lowered
            or control_type
        ):
            return UICommand(operation="list", control_type=control_type)

        if any(lowered.startswith(word) for word in _FOCUS_WORDS):
            return UICommand(
                operation="focus",
                target=AccessibilityTool._clean_target(text),
                control_type=control_type,
            )

        if any(lowered.startswith(word) for word in _CLICK_WORDS):
            return UICommand(
                operation="invoke",
                target=AccessibilityTool._clean_target(text),
                control_type=control_type,
            )

        return UICommand(operation="unknown")

    @staticmethod
    def _clean_target(text: str) -> str:
        cleaned = text.strip().strip(".!")
        lowered = cleaned.lower()

        prefixes = (
            "click on ",
            "click the ",
            "click ",
            "press the ",
            "press ",
            "invoke the ",
            "invoke ",
            "select the ",
            "select ",
            "choose the ",
            "choose ",
            "open the ",
            "open ",
            "focus on the ",
            "focus on ",
            "focus the ",
            "focus ",
            "go to the ",
            "go to ",
            "place cursor in the ",
            "place cursor in ",
        )

        for prefix in prefixes:
            if lowered.startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip()
                lowered = cleaned.lower()
                break

        for suffix in (
            " button",
            " field",
            " text field",
            " input",
            " menu item",
            " menu",
            " checkbox",
            " link",
            " hyperlink",
        ):
            if lowered.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
                break

        return cleaned.strip("'\"")

    @staticmethod
    def _detect_control_type(text: str) -> str:
        aliases = {
            "buttons": "button",
            "button": "button",
            "fields": "field",
            "field": "field",
            "inputs": "field",
            "input": "field",
            "text fields": "field",
            "menus": "menu item",
            "menu items": "menu item",
            "menu item": "menu item",
            "links": "hyperlink",
            "link": "hyperlink",
            "checkboxes": "checkbox",
            "checkbox": "checkbox",
        }

        for word, control_type in aliases.items():
            if word in text:
                return control_type

        return ""

    def _automation(self):
        from comtypes.client import CreateObject

        return CreateObject("UIAutomationClient.CUIAutomation")

    def _active_window_element(self):
        uia = self._automation()

        try:
            import win32gui

            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                return uia.ElementFromHandle(hwnd)
        except Exception:
            pass

        return uia.GetRootElement()

    def _find_elements(self, root, control_type: str = "") -> list[Any]:
        uia = self._automation()

        if control_type:
            control_type_id = _CONTROL_TYPES.get(control_type)
            if control_type_id is not None:
                condition = uia.CreatePropertyCondition(30003, control_type_id)
            else:
                condition = uia.CreateTrueCondition()
        else:
            condition = uia.CreateTrueCondition()

        collection = root.FindAll(_TREE_SCOPE_SUBTREE, condition)
        elements = []

        for index in range(collection.Length):
            element = collection.GetElement(index)
            name = self._safe_current(element, "CurrentName")

            if name:
                elements.append(element)

        return elements

    def _find_best_match(self, root, target: str, control_type: str = ""):
        target_norm = self._normalize(target)
        candidates = self._find_elements(root, control_type)
        fallback = self._find_elements(root, "") if control_type else []

        best = None
        best_score = 0

        for element in [*candidates, *fallback]:
            summary = self._summarize(element)
            score = self._score(summary, target_norm)

            if score > best_score:
                best = element
                best_score = score

        return best if best_score >= 55 else None

    def _invoke(self, element, target: str) -> ToolResult:
        element.SetFocus()

        for pattern_id, method_name in (
            (_UIA_INVOKE_PATTERN_ID, "Invoke"),
            (_UIA_SELECTION_ITEM_PATTERN_ID, "Select"),
            (_UIA_TOGGLE_PATTERN_ID, "Toggle"),
        ):
            try:
                pattern = element.GetCurrentPattern(pattern_id)
                getattr(pattern, method_name)()
                return ToolResult(success=True, message=f"Invoked '{target}'.")
            except Exception:
                continue

        return ToolResult(
            success=False,
            message=(
                f"I found '{target}', but that UI element does not expose an "
                "Invoke, Select, or Toggle accessibility pattern."
            ),
        )

    def _set_text(self, element, value: str, target: str) -> ToolResult:
        element.SetFocus()

        try:
            pattern = element.GetCurrentPattern(_UIA_VALUE_PATTERN_ID)
            pattern.SetValue(value)
            return ToolResult(success=True, message=f"Set '{target}' to: {value}")
        except Exception as error:
            return ToolResult(
                success=False,
                message=(
                    f"I found '{target}', but it does not expose a writable "
                    f"Value pattern: {error}"
                ),
            )

    def _format_elements(self, elements: list[Any], control_type: str) -> ToolResult:
        summaries = [self._summarize(element) for element in elements[:20]]

        if not summaries:
            label = control_type or "UI elements"
            return ToolResult(success=True, message=f"No {label} found in the active window.")

        lines = [
            f"- {summary.control_type}: {summary.name}"
            + (f" ({summary.automation_id})" if summary.automation_id else "")
            for summary in summaries
        ]

        return ToolResult(success=True, message="Found UI elements:\n" + "\n".join(lines))

    def _summarize(self, element) -> UIElementSummary:
        control_type_id = self._safe_current(element, "CurrentControlType")
        control_type = _CONTROL_TYPE_NAMES.get(control_type_id, str(control_type_id))

        return UIElementSummary(
            name=self._safe_current(element, "CurrentName") or "",
            control_type=control_type,
            automation_id=self._safe_current(element, "CurrentAutomationId") or "",
            class_name=self._safe_current(element, "CurrentClassName") or "",
        )

    @staticmethod
    def _safe_current(element, attribute: str):
        try:
            return getattr(element, attribute)
        except Exception:
            return ""

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().strip().split())

    def _score(self, summary: UIElementSummary, target_norm: str) -> int:
        names = [
            self._normalize(summary.name),
            self._normalize(summary.automation_id),
            self._normalize(summary.class_name),
        ]

        for name in names:
            if not name:
                continue

            if name == target_norm:
                return 100

            if target_norm in name:
                return 85

            if name in target_norm:
                return 70

            target_words = set(target_norm.split())
            name_words = set(name.split())
            if target_words and name_words:
                overlap = len(target_words & name_words) / len(target_words | name_words)
                if overlap >= 0.5:
                    return int(60 + overlap * 20)

        return 0
