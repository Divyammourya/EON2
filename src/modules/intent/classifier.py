from __future__ import annotations

import re

from src.modules.intent.models import Intent, IntentType

_URL_PATTERN = re.compile(
    r"(https?://\S+|\b[\w-]+\.(?:com|org|net|io|dev|ai|co)(?:/\S*)?\b)",
    re.IGNORECASE,
)


_VISION_SAY_PATTERN = re.compile(
    r"\bwhat does (this|that|it)\b.{0,30}\bsay\b",
    re.IGNORECASE,
)


class IntentClassifier:
    """
    Rule-based intent classifier.

    Later this will become hybrid:
    Rules + LLM + embeddings.
    """

    APP_KEYWORDS = {
        "open",
        "launch",
        "start",
        "run",
    }

    # Hindi/Hinglish equivalents for "open an app". Kept as single
    # word tokens (not phrases like "khol do"/"chalu karo") so they
    # slot into the same word-by-word trigger_index search used below
    # for English — see the SOV-order handling in the OPEN_APP branch
    # of classify() for why that matters. "do"/"karo" (the Hindi
    # auxiliary verb "do it") are handled separately, via
    # _APP_NAME_FILLER, since they're not app-opening signals on
    # their own.
    HINDI_APP_KEYWORDS = {
        "kholo",
        "khol",
        "chalu",
    }

    SEARCH_KEYWORDS = {
        "search",
        "find",
        "look up",
        "google",
    }

    # Trigger phrases checked before the generic APP_KEYWORDS so that
    # "run" isn't always treated as "launch an application" — e.g.
    # "run ipconfig in the terminal" should route to SYSTEM, not
    # OPEN_APP.
    # Real-time weather/date/time. Purely informational (read-only,
    # no side effects), but still routed through the same
    # automation-gated pipeline as everything else for consistency —
    # see WeatherTool.
    WEATHER_TRIGGERS = (
        "what's the weather",
        "whats the weather",
        "what is the weather",
        "how's the weather",
        "hows the weather",
        "weather today",
        "weather outside",
        "what's the temperature",
        "whats the temperature",
        "what is the temperature",
        "temperature outside",
        "temperature today",
        "what day is it",
        "what's the date",
        "whats the date",
        "what is the date",
        "what's today's date",
        "what time is it",
        "what's the time",
        "whats the time",
        "current time",
        # Hinglish/Hindi
        "mausam kaisa hai",
        "aaj mausam kaisa hai",
        "mausam kya hai",
        "tapman kya hai",
        "tapman kitna hai",
        "aaj kya din hai",
        "aaj ki tareekh",
        "abhi kya time hai",
        "abhi kitne baje hai",
        "kitne baj rahe hai",
    )

    # Music playback (tools/media/). Checked before the app keywords
    # below, because "start music" would otherwise be read as "launch
    # an application called music", and before TYPE_TEXT, because
    # "play" is not a typing verb.
    MUSIC_TRIGGERS = (
        "play music",
        "play some music",
        "play a song",
        "play songs",
        "play a track",
        "start music",
        "start the music",
        "start a song",
        "music bajao",
        "music chalao",
        "music play karo",
        "gaana bajao",
        "gaana chalao",
        "gana bajao",
        "gana chalao",
        "song bajao",
        "song chalao",
        "song play karo",
    )

    # "play <song>". The verb has to sit near the start: "play
    # despacito" and "can you play despacito" are requests, whereas
    # "how do i play this file" is a question *about* playing
    # something rather than a request to play it.
    _PLAY_PATTERN = re.compile(r"(?:^|\s)play\b", re.IGNORECASE)

    _MUSIC_VERB_MAX_WORDS_BEFORE = 2

    # A request names a song; a question *about* playing something does
    # not. "how do i play this file" is the case that makes this
    # necessary — the verb is only three words in, so position alone
    # doesn't rule it out.
    _MUSIC_QUESTION_WORDS = frozenset(
        {"how", "what", "why", "when", "where", "which"}
    )

    TERMINAL_TRIGGERS = (
        "run command",
        "execute command",
        "in the terminal",
        "in terminal",
        "command line",
        "terminal:",
        "cmd:",
        "shell:",
        "execute ",
    )

    # Phrases that mean "look at my screen and tell me about it",
    # checked before APP_KEYWORDS/SEARCH_KEYWORDS since none of these
    # naturally overlap with "open"/"search" phrasing.
    VISION_TRIGGERS = (
        "on my screen",
        "on the screen",
        "look at my screen",
        "look at the screen",
        "describe my screen",
        "describe the screen",
        "what do you see",
        "read my screen",
        "read the screen",
        "take a screenshot",
        "screenshot",
        "what am i looking at",
        "see my screen",
    )

    # Trailing/leading words that commonly surround an app name in
    # natural phrasing but aren't part of it (see OPEN_APP handling
    # below).
    _APP_NAME_FILLER = {
        "for",
        "me",
        "please",
        "now",
        "up",
        "the",
        "app",
        "application",
        # Hindi auxiliary/filler words that commonly trail an
        # open-app command ("notepad open karo", "notepad khol do")
        # but aren't part of the app name.
        "karo",
        "do",
        "kar",
        "ji",
    }

    # --- Deeper system control (automation/) ---------------------------
    # Checked after TERMINAL_TRIGGERS/before VISION_TRIGGERS: the
    # screenshot-save phrases below deliberately need to win against
    # VISION_TRIGGERS's plain "screenshot" substring match, since that
    # one means "describe what's on screen" rather than "save a file".

    CLIPBOARD_READ_TRIGGERS = (
        "what's on my clipboard",
        "whats on my clipboard",
        "what is on my clipboard",
        "what's in my clipboard",
        "what is in my clipboard",
        "read my clipboard",
        "read the clipboard",
        "clipboard contents",
        "what did i copy",
        "clipboard mein kya hai",
        "clipboard mein kya hain",
        "mera clipboard padho",
    )

    _CLIPBOARD_WRITE_PATTERN = re.compile(
        r"copy\s+(.+?)\s+to (?:the )?clipboard", re.IGNORECASE
    )

    SCREENSHOT_SAVE_TRIGGERS = (
        "save a screenshot",
        "save the screenshot",
        "screenshot to file",
        "screenshot and save",
        "take a screenshot and save",
        "screenshot lo",
        "screenshot bacha lo",
        "screenshot save karo",
    )

    VOLUME_TRIGGERS = (
        "volume up",
        "volume down",
        "turn up the volume",
        "turn down the volume",
        "increase the volume",
        "increase volume",
        "decrease the volume",
        "decrease volume",
        "raise the volume",
        "lower the volume",
        "set the volume",
        "set volume",
        "awaaz badhao",
        "awaaz badha do",
        "awaaz kam karo",
        "awaaz kam kar do",
        "volume badhao",
        "volume kam karo",
    )

    # "chup karo"/"chup ho jao" (be quiet) are Hindi mute phrases that
    # don't contain the literal word "mute", so they're checked
    # alongside _MUTE_PATTERN rather than folded into it.
    HINDI_MUTE_TRIGGERS = (
        "chup karo",
        "chup ho jao",
        "awaaz band karo",
    )

    _MUTE_PATTERN = re.compile(r"\b(un)?mute\b", re.IGNORECASE)

    BRIGHTNESS_TRIGGERS = (
        "brightness up",
        "brightness down",
        "increase the brightness",
        "increase brightness",
        "decrease the brightness",
        "decrease brightness",
        "set the brightness",
        "set brightness",
        "dim the screen",
        "brighten the screen",
        "screen brightness",
        "roshni badhao",
        "roshni kam karo",
        "brightness badhao",
        "brightness kam karo",
    )

    WINDOW_TRIGGERS = (
        "minimize this window",
        "minimize the window",
        "minimize window",
        "maximize this window",
        "maximize the window",
        "maximize window",
        "close this window",
        "close the window",
        "switch window to",
        "switch to",
        "bring up",
        "focus on",
        "band karo",
        "band kar do",
        "ye window band karo",
        "is window ko band karo",
    )

    ORGANIZE_TRIGGERS = (
        "organize my downloads",
        "organize the downloads folder",
        "organize downloads",
        "clean up my downloads",
        "organize my desktop",
        "organize my documents",
        "sort my downloads folder",
        "organize files in",
        "downloads ko organize karo",
        "downloads ko saaf karo",
        "saaf karo",
        "desktop saaf karo",
    )

    # --- Precise UI control via Accessibility APIs (automation/) -------
    # Finds and interacts with actual named UI elements (buttons,
    # fields, menu items) through Windows UI Automation, rather than
    # clicking at screen coordinates guessed from a screenshot — see
    # UIControlTool. UI_TYPE is checked before the generic
    # "type "/"paste " prefix check below, since "type X into the Y
    # field" is a more specific signal than plain focused-window typing.

    _UI_CLICK_PATTERN = re.compile(
        r"^(?:click|press|tap|select)\s+(?:on\s+)?(?:the\s+)?(.+)$",
        re.IGNORECASE,
    )

    _UI_CLICK_TRAILING_FILLER = (
        " button",
        " checkbox",
        " check box",
        " link",
        " tab",
        " menu item",
        " menu",
        " option",
        " icon",
        " item",
    )

    _UI_TYPE_INTO_PATTERN = re.compile(
        r"^type\s+(.+?)\s+into\s+(?:the\s+)?(.+?)(?:\s+field|\s+box|\s+input)?$",
        re.IGNORECASE,
    )

    _UI_TYPE_IN_FIELD_PATTERN = re.compile(
        r"^type\s+(.+?)\s+in\s+the\s+(.+?)\s+(?:field|box|input)$",
        re.IGNORECASE,
    )

    UI_LIST_ELEMENTS_TRIGGERS = (
        "what can i click",
        "what buttons are on this",
        "list the buttons",
        "list the ui elements",
        "what elements are on this window",
        "show me the buttons",
        "what's clickable",
        "whats clickable",
    )

    # --- Calendar / Email / Messaging (integrations/) -------------------
    # "Create"/"send" variants are checked before their "read" siblings
    # for each category, mirroring CLIPBOARD_WRITE-before-READ above —
    # same reason: the write/send trigger is the more specific signal.

    CALENDAR_CREATE_TRIGGERS = (
        "add an event",
        "create an event",
        "add event",
        "schedule a meeting",
        "schedule an appointment",
        "schedule a call",
        "add to my calendar",
        "put on my calendar",
        "book a meeting",
    )

    CALENDAR_READ_TRIGGERS = (
        "what's on my calendar",
        "whats on my calendar",
        "what is on my calendar",
        "check my calendar",
        "do i have any meetings",
        "do i have any events",
        "what meetings do i have",
        "my schedule for",
        "my calendar for",
        "upcoming events",
    )

    _EMAIL_SEND_PATTERN = re.compile(r"send (?:an? )?email", re.IGNORECASE)

    EMAIL_READ_TRIGGERS = (
        "check my email",
        "check my inbox",
        "check my emails",
        "what's in my inbox",
        "whats in my inbox",
        "do i have any new emails",
        "do i have any unread emails",
        "read my email",
        "read my inbox",
        "any new emails",
    )

    _MESSAGE_SEND_PATTERN = re.compile(
        r"send (?:a )?(?:message|text)\b", re.IGNORECASE
    )

    def _music_target(self, message: str) -> str | None:
        """Whether this is a music request, and what to pass along.

        Returns the message for the music tool to parse the song title
        out of, or ``None`` when this isn't a music request at all.

        ``None`` matters as much as a match here: "play" is an ordinary
        English word, and treating every sentence containing it as a
        music request would swallow phrasing like "how do i play this
        file".
        """
        if any(trigger in message for trigger in self.MUSIC_TRIGGERS):
            return message

        words = message.split()

        if words and words[0] in self._MUSIC_QUESTION_WORDS:
            return None

        match = self._PLAY_PATTERN.search(message)

        if match is None:
            return None

        if len(message[: match.start()].split()) > self._MUSIC_VERB_MAX_WORDS_BEFORE:
            return None

        return message

    def classify(self, text: str) -> Intent:

        message = text.lower().strip()

        # URL — checked first since it's the most specific signal.
        url_match = _URL_PATTERN.search(message)

        if url_match and any(
            trigger in message
            for trigger in ("open", "go to", "visit", "browse")
        ):
            return Intent(
                IntentType.OPEN_URL,
                target=url_match.group(0),
            )

        # Real-time weather/date/time — checked early since it's a
        # narrow, unambiguous signal with no overlap risk.
        if any(trigger in message for trigger in self.WEATHER_TRIGGERS):
            return Intent(IntentType.WEATHER, target=message)

        # Music playback — also narrow and unambiguous, and it has to
        # come before the app keywords so "start music" doesn't become
        # "launch an app".
        music_target = self._music_target(message)

        if music_target is not None:
            return Intent(IntentType.MUSIC, target=music_target)

        # Terminal / shell command.
        terminal_trigger = next(
            (
                trigger
                for trigger in self.TERMINAL_TRIGGERS
                if trigger in message
            ),
            None,
        )

        if terminal_trigger is not None:

            command = message.split(terminal_trigger, 1)[-1].strip()

            # Fall back to stripping a leading "run "/"execute " if the
            # trigger left nothing usable (e.g. "run command: dir").
            command = command.lstrip(":").strip()

            if not command:
                command = message

            return Intent(
                IntentType.SYSTEM,
                target=command,
            )

        # Deeper system control (automation/). Checked before
        # VISION_TRIGGERS so screenshot-save phrasing doesn't get
        # swallowed by VISION's plain "screenshot" substring match.
        clipboard_write_match = self._CLIPBOARD_WRITE_PATTERN.search(message)

        if clipboard_write_match:
            return Intent(
                IntentType.CLIPBOARD_WRITE,
                target=clipboard_write_match.group(1).strip(),
            )

        if any(trigger in message for trigger in self.CLIPBOARD_READ_TRIGGERS):
            return Intent(IntentType.CLIPBOARD_READ, target=message)

        if any(trigger in message for trigger in self.SCREENSHOT_SAVE_TRIGGERS):
            return Intent(IntentType.TAKE_SCREENSHOT, target=message)

        if (
            any(trigger in message for trigger in self.VOLUME_TRIGGERS)
            or self._MUTE_PATTERN.search(message)
            or any(trigger in message for trigger in self.HINDI_MUTE_TRIGGERS)
        ):
            return Intent(IntentType.VOLUME_CONTROL, target=message)

        if any(trigger in message for trigger in self.BRIGHTNESS_TRIGGERS):
            return Intent(IntentType.BRIGHTNESS_CONTROL, target=message)

        if any(trigger in message for trigger in self.WINDOW_TRIGGERS):
            return Intent(IntentType.WINDOW_CONTROL, target=message)

        if any(trigger in message for trigger in self.UI_LIST_ELEMENTS_TRIGGERS):
            return Intent(IntentType.UI_LIST_ELEMENTS, target=message)

        ui_click_match = self._UI_CLICK_PATTERN.match(text.strip())

        if ui_click_match:
            click_target = ui_click_match.group(1).strip()

            for filler in self._UI_CLICK_TRAILING_FILLER:
                if click_target.lower().endswith(filler):
                    click_target = click_target[: -len(filler)].strip()
                    break

            if click_target:
                return Intent(IntentType.UI_CLICK, target=click_target)

        if any(trigger in message for trigger in self.ORGANIZE_TRIGGERS):
            return Intent(IntentType.ORGANIZE_FILES, target=message)

        if any(trigger in message for trigger in self.CALENDAR_CREATE_TRIGGERS):
            return Intent(IntentType.CALENDAR_CREATE, target=message)

        if any(trigger in message for trigger in self.CALENDAR_READ_TRIGGERS):
            return Intent(IntentType.CALENDAR_READ, target=message)

        if self._EMAIL_SEND_PATTERN.search(message):
            return Intent(IntentType.EMAIL_SEND, target=message)

        if any(trigger in message for trigger in self.EMAIL_READ_TRIGGERS):
            return Intent(IntentType.EMAIL_READ, target=message)

        if self._MESSAGE_SEND_PATTERN.search(message):
            return Intent(IntentType.MESSAGE_SEND, target=message)

        ui_type_match = self._UI_TYPE_INTO_PATTERN.match(
            text.strip()
        ) or self._UI_TYPE_IN_FIELD_PATTERN.match(text.strip())

        if ui_type_match:
            type_value = ui_type_match.group(1).strip()
            field_name = ui_type_match.group(2).strip()

            if type_value and field_name:
                return Intent(
                    IntentType.UI_TYPE,
                    target=f"{field_name}|{type_value}",
                )

        # "likho" ("write") is the Hindi/Hinglish equivalent of the
        # "type "/"paste " prefix below.
        _TYPE_PREFIXES = ("type ", "paste ", "likho ")
        type_prefix = next(
            (p for p in _TYPE_PREFIXES if message.startswith(p)), None
        )

        if type_prefix is not None:
            return Intent(
                IntentType.TYPE_TEXT,
                target=text.strip()[len(type_prefix):].strip(),
            )

        if any(
            trigger in message for trigger in self.VISION_TRIGGERS
        ) or _VISION_SAY_PATTERN.search(message):
            return Intent(
                IntentType.VISION,
                target=message,
            )

        _all_app_keywords = self.APP_KEYWORDS | self.HINDI_APP_KEYWORDS

        if any(word in message for word in _all_app_keywords):

            aliases = {
                "code": "vscode",
                "vs code": "vscode",
                "visual studio code": "vscode",
            }

            target = ""

            if "visual studio code" in message:
                target = "visual studio code"

            elif "vs code" in message:
                target = "vs code"

            else:
                words = message.split()

                # Take what follows the trigger keyword rather than
                # blindly the last word: natural phrasing often trails
                # off after the app name ("open spotify for me", "start
                # discord now"), so anchoring on the trigger is more
                # reliable than anchoring on the end of the sentence.
                trigger_index = next(
                    (
                        i
                        for i, w in enumerate(words)
                        if w in _all_app_keywords
                    ),
                    None,
                )

                if trigger_index is not None and trigger_index + 1 < len(words):
                    candidate_words = words[trigger_index + 1:]
                elif trigger_index is not None and trigger_index > 0:
                    # Hindi/Hinglish phrasing is commonly SOV — the
                    # verb trails the object ("notepad kholo", "notepad
                    # open karo") rather than leading it ("open
                    # notepad") — so when the trigger is the last word,
                    # the app name is whatever precedes it instead.
                    candidate_words = words[:trigger_index]
                else:
                    candidate_words = words[-1:]

                candidate_words = [
                    w for w in candidate_words if w not in self._APP_NAME_FILLER
                ]

                # The words-after-trigger candidate can still end up
                # empty after filler-stripping (e.g. "notepad open
                # karo" -> ["karo"] -> [] once "karo" is filtered). Fall
                # back to the words before the trigger in that case too.
                if not candidate_words and trigger_index is not None and trigger_index > 0:
                    candidate_words = [
                        w for w in words[:trigger_index] if w not in self._APP_NAME_FILLER
                    ]

                target = " ".join(candidate_words) if candidate_words else words[-1]

            target = aliases.get(target, target)

            return Intent(
                IntentType.OPEN_APP,
                target=target,
            )

        if any(word in message for word in self.SEARCH_KEYWORDS):

            query = message

            # Strip the longest matching trigger first ("look up" before
            # "up" would ever be considered) so the leftover text is the
            # actual search query rather than a keyword fragment.
            for keyword in sorted(self.SEARCH_KEYWORDS, key=len, reverse=True):
                if keyword in query:
                    query = query.replace(keyword, "", 1)
                    break

            query = query.strip()

            # Drop a leftover leading filler word ("for"/"up") from
            # phrasing like "search for python tutorials".
            for filler in ("for ", "up "):
                if query.startswith(filler):
                    query = query[len(filler):]
                    break

            return Intent(IntentType.SEARCH_WEB, target=query.strip())

        return Intent(IntentType.CHAT)
