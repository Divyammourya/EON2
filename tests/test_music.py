"""Tests for music playback.

Nothing here launches a player or a browser: the tool takes both as
arguments, so the whole feature is exercised with the side effects
recorded instead of performed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.modules.actions.models import ActionType
from src.modules.actions.router import ActionRouter
from src.modules.intent.classifier import IntentClassifier
from src.modules.intent.models import Intent, IntentType
from src.modules.permissions.config import DEFAULT_AUTO_ACTION_TYPES
from src.modules.tools.media.music import (
    MusicTool,
    choose_random,
    find_audio_files,
    match_song,
    parse_request,
)


# --- working out what was asked for -----------------------------------------


@pytest.mark.parametrize(
    "said,expected",
    [
        # Names nothing in particular — any song will do.
        ("play music", ""),
        ("play some music", ""),
        ("play a song", ""),
        ("play something", ""),
        ("play any song", ""),
        ("play songs", ""),
        ("music bajao", ""),
        ("gaana chalao", ""),
        ("", ""),
        # Names a song.
        ("play despacito", "despacito"),
        ("play Despacito", "despacito"),
        ("play the song Despacito for me", "despacito"),
        ("play shape of you", "shape of you"),
        ("can you play despacito", "despacito"),
        ("play despacito please", "despacito"),
        ("gaana bajao despacito", "despacito"),
    ],
)
def test_parse_request(said, expected):
    assert parse_request(said) == expected


def test_a_song_title_keeps_its_own_words():
    # "song" is filler, but "Shape" and "of" are not the user's words to
    # lose — only the framing is stripped.
    assert parse_request("play the song Shape of You") == "shape of you"


# --- the library ------------------------------------------------------------


def _library(root: Path) -> Path:
    """A small, realistic music folder."""
    (root / "Despacito.mp3").write_bytes(b"x")
    (root / "Ed Sheeran - Shape of You.mp3").write_bytes(b"x")
    (root / "Justin Bieber - Despacito (feat. Daddy Yankee).m4a").write_bytes(b"x")
    (root / "notes.txt").write_text("not music", encoding="utf-8")
    (root / ".hidden.mp3").write_bytes(b"x")

    nested = root / "Albums" / "2019"
    nested.mkdir(parents=True)
    (nested / "track01.flac").write_bytes(b"x")
    (nested / "cover.jpg").write_bytes(b"x")

    return root


def test_finds_audio_files_recursively(tmp_path):
    root = _library(tmp_path)

    # Compared as a set: the order is by path (so an album's tracks sit
    # together), which is a stability property, not a promise about
    # which file comes first.
    names = {path.name for path in find_audio_files([root])}

    assert names == {
        "Despacito.mp3",
        "Ed Sheeran - Shape of You.mp3",
        "Justin Bieber - Despacito (feat. Daddy Yankee).m4a",
        "track01.flac",
    }


def test_ignores_non_audio_and_hidden_files(tmp_path):
    names = [path.name for path in find_audio_files([_library(tmp_path)])]

    assert "notes.txt" not in names
    assert "cover.jpg" not in names
    assert ".hidden.mp3" not in names


def test_a_missing_folder_is_skipped_quietly(tmp_path):
    # The defaults (~/Music, ~/Downloads) won't all exist everywhere.
    assert find_audio_files([tmp_path / "nope", _library(tmp_path)]) != []


def test_an_empty_library_is_an_empty_list(tmp_path):
    assert find_audio_files([tmp_path]) == []


def test_the_library_is_sorted_so_runs_are_stable(tmp_path):
    root = _library(tmp_path)

    assert find_audio_files([root]) == find_audio_files([root])


# --- matching a request to a file -------------------------------------------


def test_a_substring_of_the_filename_matches(tmp_path):
    files = find_audio_files([_library(tmp_path)])

    match = match_song("despacito", files)

    assert match is not None
    assert "Despacito" in match.name


def test_matching_is_case_insensitive(tmp_path):
    files = find_audio_files([_library(tmp_path)])

    assert match_song("DESPACITO", files) is not None


def test_a_multi_word_phrase_matches_across_punctuation(tmp_path):
    files = find_audio_files([_library(tmp_path)])

    match = match_song("shape of you", files)

    assert match is not None
    assert "Shape of You" in match.name


def test_word_order_does_not_matter(tmp_path):
    files = find_audio_files([_library(tmp_path)])

    match = match_song("you shape of", files)

    assert match is not None
    assert "Shape of You" in match.name


def test_most_of_a_mangled_request_still_matches(tmp_path):
    # Speech-to-text dropped a word and misspelled another.
    files = find_audio_files([_library(tmp_path)])

    match = match_song("justin despacito", files)

    assert match is not None
    assert "Justin Bieber" in match.name


def test_a_single_shared_word_is_not_enough_on_a_multi_word_request(tmp_path):
    files = find_audio_files([_library(tmp_path)])

    # "ed" appears in one file, but nothing is called this.
    assert match_song("ed madonna", files) is None


def test_nothing_close_enough_returns_none(tmp_path):
    files = find_audio_files([_library(tmp_path)])

    assert match_song("bohemian rhapsody", files) is None


def test_an_empty_query_never_matches(tmp_path):
    files = find_audio_files([_library(tmp_path)])

    assert match_song("", files) is None
    assert match_song("   ", files) is None


def test_matching_against_an_empty_library_returns_none(tmp_path):
    assert match_song("despacito", []) is None


def test_the_same_request_always_resolves_the_same_way(tmp_path):
    files = find_audio_files([_library(tmp_path)])

    assert match_song("despacito", files) == match_song("despacito", files)


# --- picking one at random --------------------------------------------------


def test_random_pick_avoids_repeating_the_last_song(tmp_path):
    files = find_audio_files([_library(tmp_path)])
    last = files[0]

    for _ in range(20):
        assert choose_random(files, avoid=last) != last


def test_random_pick_returns_the_only_song_even_if_it_just_played(tmp_path):
    only = [tmp_path / "only.mp3"]

    assert choose_random(only, avoid=only[0]) == only[0]


def test_random_pick_of_an_empty_library_is_none():
    assert choose_random([]) is None


# --- the tool ---------------------------------------------------------------


class _Recorder:
    """Stands in for a player or a browser, recording instead of acting."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, target) -> bool:
        self.calls.append(str(target))
        return True


def _tool(tmp_path, **kwargs) -> tuple[MusicTool, _Recorder, _Recorder]:
    player = _Recorder()
    opener = _Recorder()

    tool = MusicTool(
        folders=[_library(tmp_path)],
        player=player,
        opener=opener,
        **kwargs,
    )

    return tool, player, opener


def test_play_music_plays_something_from_the_library(tmp_path):
    tool, player, opener = _tool(tmp_path)

    result = tool.execute("play music")

    assert result.success
    assert len(player.calls) == 1
    assert opener.calls == []
    assert Path(player.calls[0]).suffix in {".mp3", ".m4a", ".flac"}


def test_play_music_does_not_repeat_itself(tmp_path):
    tool, player, _ = _tool(tmp_path)

    tool.execute("play music")
    first = player.calls[-1]

    tool.execute("play music")
    second = player.calls[-1]

    assert first != second


def test_play_a_named_song_plays_that_song(tmp_path):
    tool, player, opener = _tool(tmp_path)

    result = tool.execute("play despacito")

    assert result.success
    assert "Despacito" in result.message
    assert len(player.calls) == 1
    assert opener.calls == []


def test_a_song_that_isnt_downloaded_opens_a_search(tmp_path):
    tool, player, opener = _tool(tmp_path)

    result = tool.execute("play bohemian rhapsody")

    assert result.success
    assert player.calls == []
    assert len(opener.calls) == 1
    assert "bohemian+rhapsody" in opener.calls[0]
    assert "youtube" in opener.calls[0]
    assert "bohemian rhapsody" in result.message


def test_the_search_url_is_configurable(tmp_path):
    player = _Recorder()
    opener = _Recorder()
    tool = MusicTool(
        folders=[_library(tmp_path)],
        player=player,
        opener=opener,
        search_url="https://example.test/find?q={query}",
    )

    tool.execute("play bohemian rhapsody")

    assert opener.calls == ["https://example.test/find?q=bohemian+rhapsody"]


def test_an_empty_library_says_so_instead_of_failing(tmp_path):
    tool = MusicTool(folders=[tmp_path], player=_Recorder(), opener=_Recorder())

    result = tool.execute("play music")

    assert not result.success
    assert "couldn't find any music" in result.message


def test_disabling_music_says_how_to_turn_it_back_on(tmp_path):
    tool, player, _ = _tool(tmp_path, enabled=False)

    result = tool.execute("play music")

    assert not result.success
    assert "music_enabled" in result.message
    assert player.calls == []


def test_a_player_that_fails_is_reported_not_raised(tmp_path):
    def broken_player(path):
        raise RuntimeError("no audio device")

    tool = MusicTool(
        folders=[_library(tmp_path)], player=broken_player, opener=_Recorder()
    )

    result = tool.execute("play despacito")

    assert not result.success
    assert "no audio device" in result.message


def test_a_browser_that_fails_is_reported_not_raised(tmp_path):
    def broken_opener(url):
        raise RuntimeError("no browser")

    tool = MusicTool(
        folders=[_library(tmp_path)], player=_Recorder(), opener=broken_opener
    )

    result = tool.execute("play bohemian rhapsody")

    assert not result.success
    assert "no browser" in result.message


def test_the_tool_is_named_music():
    assert MusicTool().name == "music"


# --- the intent pipeline ----------------------------------------------------


@pytest.mark.parametrize(
    "said",
    [
        "play music",
        "play some music",
        "play despacito",
        "play shape of you",
        "can you play despacito",
        "start music",
        "gaana bajao",
        "music bajao",
    ],
)
def test_music_requests_are_classified_as_music(said):
    assert IntentClassifier().classify(said).type == IntentType.MUSIC


@pytest.mark.parametrize(
    "said,expected",
    [
        # "play" as an ordinary verb, buried in a sentence, is not a
        # request to play a song.
        ("how do i play this file", IntentType.CHAT),
        ("what games can i play on this laptop", IntentType.CHAT),
        # And the neighbours this must not have broken.
        ("open notepad", IntentType.OPEN_APP),
        ("search for python tutorials", IntentType.SEARCH_WEB),
        ("mausam kaisa hai", IntentType.WEATHER),
        ("what is the weather", IntentType.WEATHER),
        ("volume up", IntentType.VOLUME_CONTROL),
        ("what's on my clipboard", IntentType.CLIPBOARD_READ),
    ],
)
def test_other_intents_are_unaffected(said, expected):
    assert IntentClassifier().classify(said).type == expected


def test_start_music_is_music_not_launching_an_app():
    # "start" is an app-launch keyword, so ordering matters here.
    assert IntentClassifier().classify("start music").type == IntentType.MUSIC


def test_the_router_maps_music_to_the_music_action():
    action = ActionRouter().route(Intent(IntentType.MUSIC, target="play despacito"))

    assert action.type == ActionType.MUSIC
    assert action.target == "play despacito"


def test_music_does_not_need_a_confirmation_prompt():
    # Same risk class as VOLUME_CONTROL and OPEN_URL, both already here.
    assert ActionType.MUSIC in DEFAULT_AUTO_ACTION_TYPES
