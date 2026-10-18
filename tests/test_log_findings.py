"""Two findings from one run's log, pinned.

**The wake word was listening to noise, and to EON itself.** The log
showed:

    Wake word check heard: 'how may i assist you?'      <- EON's own line
    faster_whisper | Processing audio with duration 00:02.048   (repeated)

The listener fires when a two-second window is louder than
``wake_word_energy_threshold``, and that threshold was 300 — which is
where room noise *and* EON's own speech coming back through the speakers
sit. Ordinary speech measured 1200-3800. So the listener was running
Whisper every two seconds on noise, which is a constant CPU drain
competing with the model and a feedback loop waiting to happen.

**And `search_web` was on the router's menu.** It is the browser tool: it
opens a browser with the query and reports that it did. Routing "where is
canada" to it produced "Searching the web for 'where is canada'" instead
of an answer, when the chat path would have grounded itself and answered
properly. It is off the menu now — and still reachable by the keyword
rules, which is the property that makes removing it safe.
"""

from __future__ import annotations

from src.modules.intent.classifier import IntentClassifier
from src.modules.intent.models import IntentType
from src.modules.intent.tool_router import TOOL_DESCRIPTIONS, ToolRouter
from src.modules.voice.config import VoiceServiceConfig


# --- 1. the thresholds are inside the range that actually works ------------


def test_the_wake_word_threshold_is_above_the_noise_floor():
    """Below this, the listener transcribes room noise — and EON's own
    voice through the speakers."""
    assert VoiceServiceConfig().wake_word_energy_threshold > 300.0


def test_the_wake_word_threshold_is_below_quiet_speech():
    """Above this, it stops hearing the user. Measured speech ran
    1200-3800 RMS, so there is a wide band to sit in; this only asserts
    we are not near the top of it."""
    assert VoiceServiceConfig().wake_word_energy_threshold < 1200.0


def test_the_barge_in_default_is_reachable():
    """It was 1000, against speech measured at about 364 — so interrupting
    could never fire at the default. A default that cannot be reached is
    worse than no default."""
    assert VoiceServiceConfig().barge_in_energy_threshold <= 400.0


# --- 2. search_web is off the router's menu, but not out of reach ----------


def test_search_web_is_not_on_the_router_menu():
    assert IntentType.SEARCH_WEB not in TOOL_DESCRIPTIONS
    assert IntentType.SEARCH_WEB not in ToolRouter(ai=None, enabled=True).catalogue


class _SaysSearchWeb:
    """A model that answers ``search_web`` for everything."""

    def chat(self, messages: list[dict]) -> str:
        return "search_web"


def test_the_router_refuses_a_model_that_picks_search_web():
    """The exact bug: "where is canada" came back as "Searching the web
    for 'where is canada'". The router must decline, so the message falls
    through to chat, which answers."""
    router = ToolRouter(ai=_SaysSearchWeb(), enabled=True)

    assert router.choose("where is canada") is None


def test_search_web_is_still_caught_by_the_keyword_rules():
    """The property that makes taking it off the menu safe: an explicit
    request for it never reaches the router, because the rules place it
    first."""
    intent = IntentClassifier().classify("search the web for canada")

    assert intent.type is IntentType.SEARCH_WEB


def test_the_rest_of_the_menu_is_intact():
    """Removing one entry must not have emptied the catalogue."""
    catalogue = ToolRouter(ai=None, enabled=True).catalogue

    assert IntentType.WEATHER in catalogue
    assert IntentType.OPEN_APP in catalogue
    assert IntentType.MUSIC in catalogue
    assert len(catalogue) >= 15


def test_the_dangerous_tools_are_still_absent():
    """The allow-list reasoning is unchanged: a model choosing *which*
    tool is useful; a model inventing *what to run* is not."""
    catalogue = ToolRouter(ai=None, enabled=True).catalogue

    assert IntentType.SYSTEM not in catalogue
    assert IntentType.VISION not in catalogue
    assert IntentType.FILE not in catalogue
