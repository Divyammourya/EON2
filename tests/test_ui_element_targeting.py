"""UI actions target elements before positions.

`ui_control` drives a window by position — it finds a control and clicks
where it is. `accessibility` finds it by accessible name instead, so
"click the Save button" survives a window being moved or resized.

``accessibility`` was written, tested, and never registered, so the three
UI actions only ever reached the positional tool. These tests pin the
new order: element first, position as the fallback — and pin the one
action that deliberately did *not* move, because the two tools speak
different command shapes and typing needs a field *and* a value.
"""

from __future__ import annotations

from src.modules.actions.executor import ActionExecutor
from src.modules.actions.models import Action, ActionType
from src.modules.tools.models import ToolResult


class _Tool:
    """Records what it was asked, and answers as told."""

    def __init__(self, name: str, success: bool = True) -> None:
        self._name = name
        self.success = success
        self.commands: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    def execute(self, command: str = "") -> ToolResult:
        self.commands.append(command)

        return ToolResult(
            success=self.success,
            message=f"{self._name} ran {command!r}",
        )


def _executor(positional: _Tool, element: _Tool | None = None) -> ActionExecutor:
    executor = ActionExecutor(resources=None, tools={"ui_control": positional})

    if element is not None:
        executor._element_tool_instance = element

    return executor


def _run(executor: ActionExecutor, action_type: ActionType, target: str = "Save"):
    return executor.execute(Action(type=action_type, target=target))


# --- 1. the element tool is preferred -------------------------------------


def test_a_click_tries_the_element_tool_first():
    positional, element = _Tool("ui_control"), _Tool("accessibility")

    result = _run(_executor(positional, element), ActionType.UI_CLICK)

    assert result.success
    assert element.commands == ["click Save"]
    assert positional.commands == [], "the positional tool should not have run"


def test_listing_tries_the_element_tool_first():
    positional, element = _Tool("ui_control"), _Tool("accessibility")

    _run(_executor(positional, element), ActionType.UI_LIST_ELEMENTS)

    assert element.commands == ["list ui elements"]


def test_the_element_tool_is_given_its_own_command_shape():
    """The two tools do not speak the same language: the executor sends
    ``click:Save`` to the positional one and ``click Save`` to this."""
    positional, element = _Tool("ui_control"), _Tool("accessibility")

    _run(_executor(positional, element), ActionType.UI_CLICK, "Save")

    assert element.commands == ["click Save"]
    assert "click:Save" not in element.commands


# --- 2. the positional tool is the fallback ------------------------------------


def test_a_failing_element_tool_falls_back_to_position():
    positional = _Tool("ui_control")
    element = _Tool("accessibility", success=False)

    result = _run(_executor(positional, element), ActionType.UI_CLICK)

    assert result.success
    assert positional.commands == ["click:Save"], "the old command, unchanged"


def test_no_element_tool_still_clicks_by_position():
    """True on a machine without UI Automation, and on anything that is
    not Windows."""
    positional = _Tool("ui_control")
    executor = _executor(positional)
    executor._element_tool_instance = None

    result = _run(executor, ActionType.UI_CLICK)

    assert result.success
    assert positional.commands == ["click:Save"]


# --- 3. typing deliberately did not move ----------------------------------


def test_typing_still_goes_straight_to_the_positional_tool():
    """Typing needs a field *and* a value, which the element tool's
    command shape cannot express. It stays positional until that
    changes — a deliberate gap, not an oversight."""
    positional, element = _Tool("ui_control"), _Tool("accessibility")

    _run(_executor(positional, element), ActionType.UI_TYPE, "hello")

    assert positional.commands == ["type:hello"]
    assert element.commands == []
