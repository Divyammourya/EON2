"""Letting the model choose a tool when the keyword rules find nothing.

EON routes by keyword: ordered rules in ``IntentClassifier`` decide what
a sentence is asking for, and ``ActionRouter`` turns that into
something to do. That is fast and predictable, and it is the path
almost everything takes.

Its weakness is phrasing. When a rule doesn't match, the message falls
through to ``IntentType.CHAT`` — and the chat brain will happily *talk
about* a request it could have carried out. Ask "could you put the milk
on my list" and you get a paragraph about lists.

So this is the fallback: when the rules say CHAT, hand the model the
list of things EON can actually do and let it pick one. Only then — the
fast path is untouched — and only from a fixed catalogue.

Design notes:
    - **The catalogue is an allow-list, and a deliberate one.** It does
      not include ``SYSTEM`` (running shell commands), the ``UI_*``
      actions (clicking and typing into other applications), ``VISION``
      or ``FILE``. A model choosing *which* tool to use is useful; a
      model inventing *what to run* is not. Adding a tool here is a
      decision to trust the model with it.
    - **Choosing is not permission.** A tool picked this way still goes
      through ``ActionRouter`` → ``ActionExecutor`` → the permission
      layer, so anything risky still stops and asks. This class only
      decides what the request *meant*.
    - **Every failure is a fallback, never an error.** A model that
      answers nonsense, in the wrong language, or not at all must leave
      EON exactly as it was: chatting. So ``choose`` returns ``None``
      rather than raising, and only ever returns a tool from the
      catalogue.
    - The reply is matched exactly (case and separators normalised), not
      fuzzily. "close enough" is how a model talking about ``open_app``
      gets mistaken for choosing it.

Requires: the shared Ollama provider, via ``AIManager``.
"""

from __future__ import annotations

import re

from src.core.logger import get_logger
from src.modules.ai.manager import AIManager
from src.modules.intent.models import Intent, IntentType

logger = get_logger("ToolRouter")


#: What the model is allowed to choose from, and how each is described
#: to it. The descriptions are written for a small model: short, and in
#: the words a person would actually use rather than the enum's.
TOOL_DESCRIPTIONS: dict[IntentType, str] = {
    IntentType.OPEN_APP: "open an application or program",
    # ``SEARCH_WEB`` is deliberately absent. It is the *browser* tool —
    # it opens a browser with the query and reports that it did, and it
    # answers nothing. Putting it on this menu meant "where is canada"
    # was routed to it and came back as "Searching the web for 'where is
    # canada'", when the chat path would have grounded itself in the
    # results and actually answered. A knowledge question belongs on the
    # chat path, and an explicit "search the web for X" is caught by the
    # keyword rules before the router is ever consulted — so offering it
    # here could only ever make a question worse than not routing it.
    IntentType.OPEN_URL: "open a specific website",
    IntentType.WEATHER: "the weather or the temperature",
    IntentType.MUSIC: "play music",
    IntentType.VOLUME_CONTROL: "change or mute the volume",
    IntentType.BRIGHTNESS_CONTROL: "change the screen brightness",
    IntentType.WINDOW_CONTROL: "minimise, maximise or arrange windows",
    IntentType.TAKE_SCREENSHOT: "take a screenshot",
    IntentType.CALENDAR_READ: "read the calendar, or ask what is on it",
    IntentType.CALENDAR_CREATE: "add something to the calendar",
    IntentType.EMAIL_READ: "read or check email",
    IntentType.EMAIL_SEND: "send an email",
    IntentType.MESSAGE_SEND: "send a message to someone",
    IntentType.CLIPBOARD_READ: "read what is on the clipboard",
    IntentType.CLIPBOARD_WRITE: "copy something to the clipboard",
    IntentType.ORGANIZE_FILES: "tidy up or organise files",
    IntentType.TYPE_TEXT: "type some text into the current window",
}

#: What the model says when none of them fit.
NONE = "none"

#: Messages that are plainly conversation. A model call to check "hi"
#: against the tool catalogue costs eleven seconds on EON's machine and
#: can only ever come back "no tool" — so these never reach it.
_CONVERSATIONAL = frozenset(
    {
        "hi", "hii", "hello", "hey", "yo", "sup", "greetings",
        "thanks", "thank you", "thankyou", "thx", "ty",
        "ok", "okay", "k", "kk", "cool", "nice", "great", "good",
        "fine", "sure", "yeah", "yep", "nope", "hmm", "hm", "oh", "ah",
        "wow", "lol", "haha", "ha", "bye", "goodbye", "cya",
        "good morning", "good afternoon", "good evening", "good night",
        "how are you", "how are you doing", "how's it going",
        "hows it going", "what's up", "whats up", "who are you",
        "what is your name", "what's your name", "whats your name",
        "hi there", "hello there", "hey there", "good to see you",
    }
)

_SYSTEM = (
    "You decide which tool should handle a request. "
    "Reply with exactly one tool name from the list, and nothing else. "
    "If none of the tools fits the request, reply with NONE. "
    "Never explain, never apologise, never add punctuation."
)


def _words(reply: str) -> list[str]:
    """Splits a model's reply into comparable words.

    Everything that isn't a letter, a digit or an underscore becomes a
    separator, so ``"Open App."`` gives ``["open", "app"]`` and
    ``"open_app because it is a program"`` gives ``["open_app",
    "because", ...]``.

    Args:
        reply: Whatever the model said.

    Returns:
        Lower-case words, in order.
    """
    cleaned = reply.lower().replace("-", "_").replace("/", "_")
    return [word for word in re.split(r"[^a-z0-9_]+", cleaned) if word]


class ToolRouter:
    """Chooses a tool for a message the keyword rules could not place.

    Attributes:
        enabled: Whether it will do anything at all.
    """

    def __init__(
        self,
        ai: AIManager | None = None,
        *,
        enabled: bool | None = None,
        catalogue: dict[IntentType, str] | None = None,
    ) -> None:
        """Builds the router.

        Args:
            ai: The AI manager to ask. Defaults to a new one, which
                uses the shared provider.
            enabled: Whether to consult the model at all. ``None``
                means read ``tool_routing_enabled`` from the
                configuration, defaulting to on.
            catalogue: What the model may choose from. Defaults to
                ``TOOL_DESCRIPTIONS``; the tests pass something small.
        """
        self._ai = ai
        self._catalogue = dict(catalogue or TOOL_DESCRIPTIONS)
        self._explicit_enabled = enabled

    # --- state -----------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Whether the model will be consulted."""
        if self._explicit_enabled is not None:
            return self._explicit_enabled

        return _configured_enabled()

    @property
    def catalogue(self) -> dict[IntentType, str]:
        """The tools the model may choose from."""
        return dict(self._catalogue)

    # --- choosing --------------------------------------------------------

    def choose(self, text: str) -> Intent | None:
        """Asks the model which tool, if any, fits a message.

        Args:
            text: What the user said.

        Returns:
            An ``Intent`` for the chosen tool, or ``None`` — for a
            message that needs no tool, a reply that isn't a tool name,
            or any failure at all. Never raises: the caller is on the
            path where chatting is the correct answer anyway.
        """
        if not self.enabled:
            return None

        if not text or not text.strip():
            return None

        # Before the model is touched at all. On EON's machine this call
        # is eleven seconds, so it must not be spent on "hi" — see
        # _worth_asking for why the filter is drawn where it is.
        if not self._worth_asking(text):
            return None

        if self._ai is None:
            self._ai = AIManager()

        try:
            reply = self._ai.chat(self._build_messages(text))
        except Exception as error:
            logger.warning("Tool routing failed, falling back to chat: %s", error)
            return None

        return self._interpret(reply, text)

    @staticmethod
    def _worth_asking(text: str) -> bool:
        """Whether ``text`` could plausibly be a request for a tool.

        This is a cost filter, not a classifier. Consulting the model
        costs a full call, and on a small machine that is eleven
        seconds — so a message that can only ever come back "no tool"
        should never be sent.

        Deliberately narrow. It drops a whole message that is *only*
        an acknowledgement or a greeting, and nothing else.

        An earlier version of this also skipped short messages, on the
        theory that brevity means small talk. That was wrong, and the
        tests caught it: "start notepad" is a two-word request and
        "screenshot" is a one-word one. Length says nothing about
        intent, so length is not used here. The only thing this filter
        knows is a fixed list of phrases that cannot be requests,
        because the catalogue has no tool any of them could want.

        Args:
            text: What the user said.

        Returns:
            ``True`` if the model should be asked.
        """
        stripped = text.strip()

        if not stripped:
            return False

        return stripped.rstrip("!.?,").lower() not in _CONVERSATIONAL

    def _interpret(self, reply: str, text: str) -> Intent | None:
        """Turns the model's reply into an Intent, or nothing.

        Args:
            reply: What the model said.
            text: The original message, which becomes the intent's
                target — the tools expect the whole sentence, since
                they parse it themselves.
        """
        if not reply:
            return None

        words = _words(reply)

        if not words:
            return None

        if NONE in words:
            return None

        # A small model asked for one word will still sometimes write
        # "open app" for ``open_app``, so the whole reply joined back up
        # is checked too, not just its individual words.
        joined = "_".join(words)

        for intent_type in self._catalogue:
            if intent_type.value == joined or intent_type.value in words:
                logger.info(
                    "Tool routing: %r -> %s", text[:60], intent_type.value
                )
                return Intent(intent_type, target=text)

        # A tool the model invented, or one deliberately not on offer
        # (run_command, the UI automations) — treat it as "no tool".
        logger.info(
            "Tool routing: model answered %r for %r, which is not on offer",
            reply[:40],
            text[:60],
        )
        return None

    def _build_messages(self, text: str) -> list[dict]:
        """The prompt: the catalogue, then the request."""
        lines = [
            f"- {intent_type.value}: {description}"
            for intent_type, description in self._catalogue.items()
        ]

        return [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    "Tools:\n"
                    + "\n".join(lines)
                    + f"\n\nRequest: {text}\n\nTool name:"
                ),
            },
        ]


def _configured_enabled() -> bool:
    """Reads ``tool_routing_enabled`` from the configuration.

    Read once per call rather than cached, so flipping the setting and
    restarting is enough. A missing key, or a configuration that can't
    be loaded, means on: the feature is only ever a fallback, so its
    absence should not silently disable it.

    Returns:
        Whether tool routing should run.
    """
    try:
        from src.core.config import ConfigManager

        value = ConfigManager().get("tool_routing_enabled")
    except Exception as error:
        logger.debug("Could not read tool_routing_enabled: %s", error)
        return True

    if value is None:
        return True

    return bool(value)
