"""
Action models.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionType(str, Enum):
    """Types of actions EON can perform."""

    CHAT = "chat"
    OPEN_APP = "open_app"
    SEARCH_WEB = "search_web"
    RUN_COMMAND = "run_command"
    OPEN_URL = "open_url"
    VIEW_SCREEN = "view_screen"
    CLIPBOARD_READ = "clipboard_read"
    CLIPBOARD_WRITE = "clipboard_write"
    VOLUME_CONTROL = "volume_control"
    BRIGHTNESS_CONTROL = "brightness_control"
    WINDOW_CONTROL = "window_control"
    TAKE_SCREENSHOT = "take_screenshot"
    ORGANIZE_FILES = "organize_files"
    TYPE_TEXT = "type_text"
    UI_CLICK = "ui_click"
    UI_TYPE = "ui_type"
    UI_LIST_ELEMENTS = "ui_list_elements"
    CALENDAR_READ = "calendar_read"
    CALENDAR_CREATE = "calendar_create"
    EMAIL_READ = "email_read"
    EMAIL_SEND = "email_send"
    MESSAGE_SEND = "message_send"
    WEATHER = "weather"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class Action:
    """Represents an executable action."""

    type: ActionType
    target: str = ""

@dataclass(slots=True)
class ActionResult:
    """Result returned after executing an action."""

    success: bool

    message: str
