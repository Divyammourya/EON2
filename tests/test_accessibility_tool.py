from src.modules.automation.accessibility import AccessibilityTool


def test_parse_click_button_command() -> None:
    command = AccessibilityTool.parse_command("click the Submit button")

    assert command.operation == "invoke"
    assert command.target == "Submit"
    assert command.control_type == "button"


def test_parse_set_text_command() -> None:
    command = AccessibilityTool.parse_command("type hello into search field")

    assert command.operation == "set_text"
    assert command.target == "search"
    assert command.value == "hello"
    assert command.control_type == "field"


def test_parse_list_buttons_command() -> None:
    command = AccessibilityTool.parse_command("list buttons")

    assert command.operation == "list"
    assert command.control_type == "button"
