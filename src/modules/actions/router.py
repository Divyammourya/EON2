"""
Action Router.
"""

from __future__ import annotations

from src.modules.actions.models import Action, ActionType
from src.modules.intent.models import Intent, IntentType


class ActionRouter:
    """Converts an Intent into an Action."""

    def route(self, intent: Intent) -> Action:

        mapping = {
            IntentType.CHAT: ActionType.CHAT,
            IntentType.OPEN_APP: ActionType.OPEN_APP,
            IntentType.SEARCH_WEB: ActionType.SEARCH_WEB,
            IntentType.SYSTEM: ActionType.RUN_COMMAND,
            IntentType.OPEN_URL: ActionType.OPEN_URL,
            IntentType.VISION: ActionType.VIEW_SCREEN,
            IntentType.CLIPBOARD_READ: ActionType.CLIPBOARD_READ,
            IntentType.CLIPBOARD_WRITE: ActionType.CLIPBOARD_WRITE,
            IntentType.VOLUME_CONTROL: ActionType.VOLUME_CONTROL,
            IntentType.BRIGHTNESS_CONTROL: ActionType.BRIGHTNESS_CONTROL,
            IntentType.WINDOW_CONTROL: ActionType.WINDOW_CONTROL,
            IntentType.TAKE_SCREENSHOT: ActionType.TAKE_SCREENSHOT,
            IntentType.ORGANIZE_FILES: ActionType.ORGANIZE_FILES,
            IntentType.TYPE_TEXT: ActionType.TYPE_TEXT,
            IntentType.UI_CLICK: ActionType.UI_CLICK,
            IntentType.UI_TYPE: ActionType.UI_TYPE,
            IntentType.UI_LIST_ELEMENTS: ActionType.UI_LIST_ELEMENTS,
            IntentType.CALENDAR_READ: ActionType.CALENDAR_READ,
            IntentType.CALENDAR_CREATE: ActionType.CALENDAR_CREATE,
            IntentType.EMAIL_READ: ActionType.EMAIL_READ,
            IntentType.EMAIL_SEND: ActionType.EMAIL_SEND,
            IntentType.MESSAGE_SEND: ActionType.MESSAGE_SEND,
            IntentType.WEATHER: ActionType.WEATHER,
            IntentType.MUSIC: ActionType.MUSIC,
        }

        action_type = mapping.get(intent.type, ActionType.UNKNOWN)

        return Action(
            type=action_type,
            target=intent.target,
        )
