"""Lists and notes: the small things you ask an assistant to hold.

Why this exists
---------------
"Add milk to my shopping list" and "what's on my shopping list" are the
most ordinary things anyone asks an assistant, and EON had nowhere to put
the answer. This gives it named lists (a to-do list, a shopping list, any
list you name) plus quick notes, stored as plain JSON so you can read and
edit the file yourself.

Design
------
Parsing is pure and unit tested; only ``ListStore`` touches the disk.
Matching is deliberately strict — if a message doesn't clearly name a
list, this returns None and the message falls through to normal chat
rather than being captured and mis-stored.

Requires: Python 3.12+
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("Lists")

DEFAULT_LISTS_PATH = Path("data") / "lists.json"

# The list that "note that ..." and "make a note ..." write to.
NOTES = "notes"

# The list "mark X as done" assumes when no list is named.
DEFAULT_TODO = "todo"

_ADD = re.compile(
    r"^\s*(?:please\s+)?(?:add|put|append|stick)\s+(?P<item>.+?)"
    r"\s+(?:to|on|onto|into)\s+(?P<rest>.+)$",
    re.I,
)
_REMOVE = re.compile(
    r"^\s*(?:please\s+)?(?:remove|delete|drop|take|tick off|check off)\s+"
    r"(?P<item>.+?)\s+(?:from|off)\s+(?P<rest>.+)$",
    re.I,
)
_DONE = re.compile(
    r"^\s*(?:please\s+)?(?:mark|tick|check)\s+(?P<item>.+?)\s+"
    r"(?:as\s+)?(?:done|complete|completed|finished)\b(?P<rest>.*)$",
    re.I,
)
_CLEAR = re.compile(
    r"^\s*(?:please\s+)?(?:clear|empty|wipe|reset)\s+(?P<rest>.+)$",
    re.I,
)
_SHOW = re.compile(
    r"^\s*(?:please\s+)?(?:what(?:'s| is)?\s+on|show|read|display|list)\s+"
    r"(?P<rest>.+)$",
    re.I,
)
_NOTE = re.compile(
    r"^\s*(?:please\s+)?(?:make\s+a\s+note|note|jot\s+down)\s*"
    r"(?:that|:)?\s*(?P<item>.+)$",
    re.I,
)

_LIST_NAME = re.compile(
    r"\b(?:(?:my|the|a)\s+)?([a-z0-9][a-z0-9 \-]{0,30}?)\s+list\b",
    re.I,
)
_BARE_LIST = re.compile(r"\b(?:my|the)\s+list\b", re.I)
_NOTES_REF = re.compile(r"\bnotes?\b", re.I)


@dataclass(slots=True)
class Command:
    """One recognised list action."""

    action: str  # "add" | "remove" | "clear" | "show"
    list_name: str
    item: str = ""


def _list_name(text: str) -> str | None:
    """Extracts the list being referred to, or None if none is named."""
    match = _LIST_NAME.search(text)

    if match:
        name = re.sub(r"\s+", " ", match.group(1).strip().lower())
        name = name.replace("to-do", DEFAULT_TODO).replace("to do", DEFAULT_TODO)
        if name:
            return name

    if _NOTES_REF.search(text):
        return NOTES

    if _BARE_LIST.search(text):
        return DEFAULT_TODO

    return None


def _clean_item(item: str) -> str:
    return item.strip().strip(".").strip()


def parse_command(text: str) -> Command | None:
    """Turns a message into a list action, or returns None.

    Pure: it recognises and describes, it does not touch the store.
    Returns None for anything it isn't confident about, so ordinary
    conversation is never mistaken for a list instruction.
    """
    stripped = text.strip()

    if not stripped:
        return None

    note = _NOTE.match(stripped)
    if note:
        item = _clean_item(note.group("item"))
        if item:
            return Command(action="add", list_name=NOTES, item=item)

    add = _ADD.match(stripped)
    if add:
        name = _list_name(add.group("rest"))
        item = _clean_item(add.group("item"))
        if name and item:
            return Command(action="add", list_name=name, item=item)

    remove = _REMOVE.match(stripped)
    if remove:
        name = _list_name(remove.group("rest"))
        item = _clean_item(remove.group("item"))
        if name and item:
            return Command(action="remove", list_name=name, item=item)

    done = _DONE.match(stripped)
    if done:
        name = (
            _list_name(done.group("rest"))
            or _list_name(stripped)
            or DEFAULT_TODO
        )
        item = _clean_item(done.group("item"))
        if name and item:
            return Command(action="remove", list_name=name, item=item)

    clear = _CLEAR.match(stripped)
    if clear:
        name = _list_name(clear.group("rest"))
        if name:
            return Command(action="clear", list_name=name)

    show = _SHOW.match(stripped)
    if show:
        name = _list_name(show.group("rest"))
        if name:
            return Command(action="show", list_name=name)

    return None


def _label(name: str) -> str:
    """A human phrase for a list name, for use in replies."""
    if name == NOTES:
        return "notes"
    if name == DEFAULT_TODO:
        return "to-do list"
    return f"{name} list"


class ListStore:
    """A small JSON-backed store of named lists.

    The file is plain JSON so it stays readable and editable by hand:

        {"shopping": ["milk", "eggs"], "todo": ["call the bank"]}
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = Path(path) if path is not None else DEFAULT_LISTS_PATH
        self._lists: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning(
                "Could not read %s; starting with empty lists.",
                self._path,
            )
            return

        if isinstance(data, dict):
            self._lists = {
                str(name): [str(item) for item in items]
                for name, items in data.items()
                if isinstance(items, list)
            }

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._lists, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            logger.exception("Could not save lists to %s.", self._path)

    def items(self, name: str) -> list[str]:
        """The items on a list, oldest first."""
        return list(self._lists.get(name, []))

    def add(self, name: str, item: str) -> bool:
        """Adds an item. Returns False if it was already there."""
        existing = self._lists.setdefault(name, [])

        for current in existing:
            if current.lower() == item.lower():
                return False

        existing.append(item)
        self._save()
        return True

    def remove(self, name: str, item: str) -> bool:
        """Removes an item. Returns False if it wasn't there."""
        existing = self._lists.get(name)

        if not existing:
            return False

        for index, current in enumerate(existing):
            if current.lower() == item.lower():
                existing.pop(index)
                self._save()
                return True

        return False

    def clear(self, name: str) -> None:
        """Empties a list, keeping the list itself."""
        if name in self._lists:
            self._lists[name] = []
            self._save()


def handle(text: str, store: ListStore) -> str | None:
    """Runs a list command against ``store``, or returns None.

    Returns the reply to say back to the user, or None when the message
    wasn't a list command at all.
    """
    command = parse_command(text)

    if command is None:
        return None

    label = _label(command.list_name)

    if command.action == "add":
        if store.add(command.list_name, command.item):
            return f'Added "{command.item}" to your {label}.'
        return f'"{command.item}" is already on your {label}.'

    if command.action == "remove":
        if store.remove(command.list_name, command.item):
            return f'Removed "{command.item}" from your {label}.'
        return f'I couldn\'t find "{command.item}" on your {label}.'

    if command.action == "clear":
        store.clear(command.list_name)
        return f"Cleared your {label}."

    items = store.items(command.list_name)

    if not items:
        return f"Your {label} is empty."

    listing = "\n".join(f"- {item}" for item in items)
    return f"Your {label}:\n{listing}"
