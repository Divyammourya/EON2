"""Two places where EON matched things too loosely.

Both were found in the same run log, and they share a cause: a matcher
that accepted a partial match where only a real one should do.

    1. The application launcher's "query contains the app's name" rule
       had no word boundary and no minimum length. A registry entry
       called ``od`` is a substring of ``coding``, so typing
       ``open coding workspace`` scored 60 for it, it beat everything
       else, and EON launched a two-letter application. The log said
       ``od launched successfully.``

    2. The coding mode's trigger list didn't include ``open coding
       workspace``, so that phrasing never reached it — the brain read
       "workspace" as an application to launch instead. (Which is how
       the first bug got triggered.)
"""

from __future__ import annotations

import pytest

from src.modules.tools.launcher.models import Application
from src.modules.tools.launcher.registry import ApplicationRegistry
from src.modules.tools.launcher.resolver_engine import ApplicationResolver
from src.modules.workspace.workspaces.coding.mode import parse_coding_request


def _resolver(*apps: Application) -> ApplicationResolver:
    registry = ApplicationRegistry()

    for app in apps:
        registry.register(app)

    return ApplicationResolver(registry)


# --- the launcher -----------------------------------------------------------


def test_a_two_letter_app_no_longer_matches_an_unrelated_query():
    # The bug from the log: "od" is inside "coding".
    resolver = _resolver(Application(name="od", path="C:/fake/od.exe"))

    assert resolver.resolve("coding workspace") is None


def test_a_short_name_inside_another_word_does_not_match():
    resolver = _resolver(Application(name="pad", path="C:/fake/pad.exe"))

    assert resolver.resolve("open the notepad app") is None


def test_a_real_name_still_matches_a_query_with_extra_words():
    # The case the reverse-contains rule exists for.
    notepad = Application(name="notepad", path="C:/fake/notepad.exe")
    resolver = _resolver(notepad)

    assert resolver.resolve("open the notepad app") is notepad


def test_the_name_must_be_a_whole_word():
    word = Application(name="word", path="C:/fake/word.exe")
    resolver = _resolver(word)

    assert resolver.resolve("open word") is word
    # "swordfish" merely contains "word"; it is not the word.
    assert resolver.resolve("open swordfish") is None


def test_the_right_app_wins_over_a_short_one():
    # The real-world shape of the bug: a junk short entry competing
    # with the app actually asked for.
    junk = Application(name="od", path="C:/fake/od.exe")
    vscode = Application(name="code", path="C:/fake/code.exe")
    resolver = _resolver(junk, vscode)

    assert resolver.resolve("open code") is vscode


def test_an_exact_name_still_wins():
    chrome = Application(name="chrome", path="C:/fake/chrome.exe")
    resolver = _resolver(chrome)

    assert resolver.resolve("chrome") is chrome


def test_a_name_longer_than_the_query_still_matches():
    # "chrome" inside "google chrome" — the forward-contains rule.
    chrome = Application(name="google chrome", path="C:/fake/chrome.exe")
    resolver = _resolver(chrome)

    assert resolver.resolve("chrome") is chrome


def test_aliases_still_work():
    vscode = Application(
        name="visual studio code",
        path="C:/fake/code.exe",
        aliases=["vs code"],
    )
    resolver = _resolver(vscode)

    assert resolver.resolve("vs code") is vscode


# --- the coding triggers ----------------------------------------------------


@pytest.mark.parametrize(
    "said",
    [
        "coding",
        "coding workspace",
        "the coding workspace",
        "coding mode",
        "code mode",
        "code workspace",
        "open coding workspace",
        "open coding mode",
        "start coding",
        "Open Coding Workspace",
    ],
)
def test_phrasings_that_enter_coding_mode(said):
    request = parse_coding_request(said)

    assert request is not None, f"{said!r} should enter coding mode"
    assert request.project == ""


@pytest.mark.parametrize(
    "said",
    [
        "open notepad",
        "open chrome",
        "open project thing",
        "what's the weather",
        "play music",
        "",
    ],
)
def test_phrasings_that_do_not(said):
    assert parse_coding_request(said) is None


def test_naming_a_project_still_works_with_open():
    request = parse_coding_request("open coding calculator")

    assert request is not None
    assert request.project == "calculator"
