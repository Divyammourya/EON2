"""Tests for the local utility skills: calculator, units, lists.

Everything here is pure or uses a temporary file — no network, no model.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.modules.tools.utility import calculator, lists, units
from src.modules.tools.utility.lists import ListStore
from src.modules.tools.utility.skills import LocalSkills


@pytest.fixture()
def store(tmp_path: Path) -> ListStore:
    return ListStore(tmp_path / "lists.json")


# --- calculator --------------------------------------------------------


def test_percentages():
    assert calculator.answer("what is 18% of 4500") == "18% of 4500 is 810."
    assert calculator.answer("10 percent of 250") == "10% of 250 is 25."


def test_plain_arithmetic():
    assert calculator.answer("2 + 2") == "2 + 2 = 4"
    assert calculator.answer("what's 12 * 7") == "12 * 7 = 84"
    assert calculator.answer("100 / 8") == "100 / 8 = 12.5"


def test_spoken_operators():
    assert calculator.answer("calculate 45 divided by 9") == "45 / 9 = 5"
    assert calculator.answer("3 times 4") == "3 * 4 = 12"
    assert calculator.answer("what is 2 to the power of 10") == "2 ** 10 = 1024"


def test_prose_is_not_treated_as_arithmetic():
    assert calculator.answer("hello there") is None
    assert calculator.answer("who is the president") is None
    assert calculator.answer("add 2 kg of rice to my shopping list") is None


def test_dangerous_input_is_refused():
    # Nothing here uses eval, but prove it: no calls, names or imports.
    assert calculator.answer('__import__("os").system("ls")') is None
    assert calculator.answer("open('/etc/passwd')") is None


def test_huge_exponents_are_refused():
    # 9 ** 9 ** 9 would hang or exhaust memory.
    assert calculator.answer("9 ** 9 ** 9") is None


def test_division_by_zero_is_not_an_answer():
    assert calculator.answer("what is 10 / 0") is None


# --- units -------------------------------------------------------------


def test_length_and_mass():
    assert units.answer("10 km in miles") == "10 km is 6.2137 miles."
    assert units.answer("70 kg in pounds") == "70 kg is 154.3236 pounds."


def test_temperature_uses_degree_symbols():
    assert units.answer("30 celsius in fahrenheit") == "30°C is 86°F."
    assert units.answer("100 f to c") == "100°F is 37.7778°C."


def test_time_and_volume():
    assert units.answer("2 hours in minutes") == "2 hours is 120 minutes."
    assert units.answer("5 litres in ml") == "5 litres is 5000 ml."


def test_cross_family_conversion_is_refused():
    # Kilograms are not kilometres. Guessing would be worse than silence.
    assert units.answer("5 kg in km") is None


def test_prose_is_not_treated_as_a_conversion():
    assert units.answer("I went to the market in the morning") is None
    assert units.answer("3 days in Paris") is None


# --- lists: parsing ----------------------------------------------------


def test_add_command():
    command = lists.parse_command("add milk to my shopping list")

    assert command == lists.Command(
        action="add", list_name="shopping", item="milk"
    )


def test_add_command_with_a_hyphenated_list():
    command = lists.parse_command("add call the bank to my to-do list")

    assert command is not None
    assert command.list_name == "todo"
    assert command.item == "call the bank"


def test_show_command():
    command = lists.parse_command("what's on my shopping list")

    assert command is not None
    assert command.action == "show"
    assert command.list_name == "shopping"


def test_remove_command():
    command = lists.parse_command("remove milk from my shopping list")

    assert command is not None
    assert command.action == "remove"
    assert command.item == "milk"


def test_mark_done_removes_from_the_todo_list():
    command = lists.parse_command("mark call the bank as done")

    assert command is not None
    assert command.action == "remove"
    assert command.list_name == "todo"


def test_clear_command():
    command = lists.parse_command("clear my shopping list")

    assert command is not None
    assert command.action == "clear"


def test_notes():
    command = lists.parse_command("note that the wifi password is hunter2")

    assert command is not None
    assert command.list_name == lists.NOTES
    assert command.item == "the wifi password is hunter2"


def test_show_notes():
    command = lists.parse_command("show my notes")

    assert command is not None
    assert command.list_name == lists.NOTES


def test_ordinary_chat_is_not_a_list_command():
    # The whole point: a message that isn't a clear list instruction must
    # fall through to the model rather than being captured.
    assert lists.parse_command("how are you") is None
    assert lists.parse_command("add 2 and 3") is None
    assert lists.parse_command("") is None


# --- lists: the store --------------------------------------------------


def test_add_and_read_back(store: ListStore):
    assert store.add("shopping", "milk") is True
    assert store.add("shopping", "eggs") is True

    assert store.items("shopping") == ["milk", "eggs"]


def test_duplicates_are_refused_case_insensitively(store: ListStore):
    store.add("shopping", "Milk")

    assert store.add("shopping", "milk") is False
    assert store.items("shopping") == ["Milk"]


def test_remove(store: ListStore):
    store.add("shopping", "milk")

    assert store.remove("shopping", "milk") is True
    assert store.remove("shopping", "milk") is False
    assert store.items("shopping") == []


def test_clear_keeps_the_list(store: ListStore):
    store.add("shopping", "milk")

    store.clear("shopping")

    assert store.items("shopping") == []


def test_lists_persist_to_disk(tmp_path: Path):
    path = tmp_path / "lists.json"

    first = ListStore(path)
    first.add("shopping", "milk")

    second = ListStore(path)

    assert second.items("shopping") == ["milk"]


def test_a_corrupt_file_does_not_crash(tmp_path: Path):
    path = tmp_path / "lists.json"
    path.write_text("{ this is not json", encoding="utf-8")

    store = ListStore(path)

    assert store.items("shopping") == []


# --- lists: replies ----------------------------------------------------


def test_handle_adds_and_lists(store: ListStore):
    assert lists.handle("add milk to my shopping list", store) == (
        'Added "milk" to your shopping list.'
    )
    assert lists.handle("add eggs to my shopping list", store) == (
        'Added "eggs" to your shopping list.'
    )
    assert lists.handle("what's on my shopping list", store) == (
        "Your shopping list:\n- milk\n- eggs"
    )


def test_handle_reports_an_empty_list(store: ListStore):
    assert lists.handle("what's on my shopping list", store) == (
        "Your shopping list is empty."
    )


def test_handle_reports_a_missing_item(store: ListStore):
    assert lists.handle("remove milk from my shopping list", store) == (
        'I couldn\'t find "milk" on your shopping list.'
    )


def test_handle_returns_none_for_chat(store: ListStore):
    assert lists.handle("how are you", store) is None


# --- the dispatcher ----------------------------------------------------


def test_skills_answer_list_commands_before_arithmetic(store: ListStore):
    # "add 2 kg of rice to my shopping list" looks arithmetic-ish; it is
    # a list command and must not be captured by the calculator.
    skills = LocalSkills(store=store)

    assert skills.answer("add 2 kg of rice to my shopping list") == (
        'Added "2 kg of rice" to your shopping list.'
    )


def test_skills_answer_arithmetic_and_conversions(store: ListStore):
    skills = LocalSkills(store=store)

    assert skills.answer("what is 18% of 4500") == "18% of 4500 is 810."
    assert skills.answer("10 km in miles") == "10 km is 6.2137 miles."


def test_skills_fall_through_for_ordinary_chat(store: ListStore):
    skills = LocalSkills(store=store)

    assert skills.answer("tell me a story") is None


def test_disabled_skills_answer_nothing(store: ListStore):
    skills = LocalSkills(store=store, enabled=False)

    assert skills.answer("what is 18% of 4500") is None
    assert skills.answer("add milk to my shopping list") is None
