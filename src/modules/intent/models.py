from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IntentType(str, Enum):
    CHAT = "chat"
    OPEN_APP = "open_app"
    SEARCH_WEB = "search_web"
    FILE = "file"
    SYSTEM = "system"
    OPEN_URL = "open_url"
    VISION = "vision"
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
class Intent:
    type: IntentType
    confidence: float = 1.0
    target: str = ""
