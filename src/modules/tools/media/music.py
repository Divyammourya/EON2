"""Music Tool.

Plays a song from the user's own music folders, and falls back to
searching YouTube in the browser when the song isn't downloaded.

The three things someone can ask for, and what each one does:

    "play music"        -> any downloaded song, picked at random
    "play despacito"    -> that song, if it's in the library
    "play <not owned>"  -> opens a YouTube search for it

Design notes:
    - Playback is handed to the operating system's default audio player
      (``os.startfile`` on Windows, ``open``/``xdg-open`` elsewhere).
      That means no new dependency and no bundled codec, and EON plays
      whatever the machine can already play. The trade-off is that EON
      can't pause, skip or stop what it started — it hands the file
      over and steps back.
    - Matching is forgiving on purpose. Filenames are messy
      ("01 - Despacito (feat. Daddy Yankee).mp3") and speech-to-text is
      messier still, so a request is matched on token overlap rather
      than on equality. A single shared word is never enough, though —
      otherwise "play music" would match whatever track happens to have
      the word in its name.
    - Opening a YouTube *search* is the honest limit of the fallback.
      Resolving the top hit and playing it directly needs a downloader
      like yt-dlp, which is a heavier dependency than this feature
      warrants. The search page is one click away from playing.

Requires: Python 3.12+ (no extra packages)
"""

from __future__ import annotations

import os
import random
import re
import subprocess
import sys
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import quote_plus

from src.core.logger import get_logger
from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

logger = get_logger("Music")

# Everything the default players on Windows/macOS/Linux commonly handle.
AUDIO_EXTENSIONS = frozenset(
    {
        ".mp3",
        ".m4a",
        ".aac",
        ".wav",
        ".flac",
        ".ogg",
        ".oga",
        ".opus",
        ".wma",
        ".aiff",
        ".alac",
    }
)

# Where to look when the user hasn't configured anything. Both are
# guesses about a normal machine rather than anything EON-specific.
DEFAULT_MUSIC_FOLDERS = ("~/Music", "~/Downloads")

YOUTUBE_SEARCH_URL = "https://www.youtube.com/results?search_query={query}"

# Words that mean "any song will do" rather than naming one. Includes
# the Hinglish words, since a spoken "gaana bajao" is just as likely as
# "play music".
_ANY_SONG_WORDS = frozenset(
    {
        "music",
        "song",
        "songs",
        "track",
        "tracks",
        "something",
        "anything",
        "whatever",
        "gaana",
        "gana",
        "sangeet",
        "kuch",
        "koi",
        "any",
    }
)

# The English verb is SVO, so a title is whatever follows it — cutting
# there is more accurate than stripping filler, because it can't eat a
# word that belongs to the song. The Hinglish verbs are handled as
# filler instead of cut on, because they can sit on either side of the
# title ("gaana bajao despacito", "despacito bajao").
_VERB_WORDS = ("play", "start")

# Words that surround a song title in natural phrasing but aren't part
# of it. Stripped before matching, so "play the song Despacito for me"
# looks for "despacito".
_FILLER_WORDS = frozenset(
    {
        "play",
        "please",
        "me",
        "some",
        "a",
        "an",
        "the",
        "for",
        "put",
        "on",
        "song",
        "songs",
        "music",
        "track",
        "tracks",
        "bajao",
        "baja",
        "bajado",
        "chalao",
        "chala",
        "karo",
        "kar",
        "do",
        "de",
        "gaana",
        "gana",
    }
)

_WORD_PATTERN = re.compile(r"[\w'&-]+")


def parse_request(text: str) -> str:
    """Works out which song the user asked for.

    Args:
        text: What the user said, e.g. "play the song Despacito for me".

    Returns:
        The song title to look for, or ``""`` when they didn't name one
        — which means "any song will do".
    """
    words = _WORD_PATTERN.findall(text.lower())

    for verb in _VERB_WORDS:
        if verb in words:
            words = words[words.index(verb) + 1 :]
            break

    remaining = [word for word in words if word not in _FILLER_WORDS]

    if not remaining:
        return ""

    # "play something" / "play any song" name nothing in particular.
    if all(word in _ANY_SONG_WORDS for word in remaining):
        return ""

    return " ".join(remaining)


def find_audio_files(folders: Sequence[str | Path]) -> list[Path]:
    """Every audio file under the given folders, sorted.

    Walks each folder recursively and skips hidden files. Sorting keeps
    the library stable between runs, which matters because the random
    pick is seeded from it.

    A folder that doesn't exist is skipped silently — the defaults
    (``~/Music``, ``~/Downloads``) won't all exist on every machine,
    and that is not an error worth reporting.

    Args:
        folders: Folders to search, in order.

    Returns:
        The matching files.
    """
    found: list[Path] = []

    for folder in folders:
        root = Path(folder).expanduser()

        if not root.is_dir():
            continue

        try:
            candidates = list(root.rglob("*"))
        except OSError as error:
            logger.warning("Could not scan %s for music: %s", root, error)
            continue

        for path in candidates:
            try:
                if not path.is_file() or path.name.startswith("."):
                    continue
            except OSError:
                continue

            if path.suffix.lower() in AUDIO_EXTENSIONS:
                found.append(path)

    return sorted(found)


def match_song(query: str, files: Sequence[Path]) -> Path | None:
    """The library file that best answers ``query``, or ``None``.

    Forgiving on purpose, in this order:

    1. The whole query appears in the filename — so "shape of you"
       finds "Ed Sheeran - Shape of You.mp3".
    2. Every word of the query appears somewhere in the filename, in
       any order — so "despacito justin" finds
       "Justin Bieber - Despacito.mp3".
    3. Most words overlap, which is what rescues a request that
       speech-to-text mangled slightly.

    A single shared word is never enough on a multi-word request, and
    ties are broken by path so the same request always resolves the
    same way.

    Args:
        query: The song to look for.
        files: The library to look in.

    Returns:
        The best match, or ``None`` if nothing is close enough.
    """
    cleaned = query.strip().lower()

    if not cleaned:
        return None

    # Single-character words are noise ("a", "o") and match everything.
    query_words = [word for word in _WORD_PATTERN.findall(cleaned) if len(word) > 1]

    if not query_words:
        return None

    scored: list[tuple[float, Path]] = []

    for path in files:
        name = path.stem.lower()

        if cleaned in name:
            scored.append((1.0, path))
            continue

        name_words = set(_WORD_PATTERN.findall(name))
        overlap = sum(1 for word in query_words if word in name_words)

        if overlap == 0:
            continue

        if len(query_words) > 1 and overlap < 2:
            # One shared word between two different titles is a
            # coincidence, not a match.
            continue

        scored.append((overlap / len(query_words), path))

    if not scored:
        return None

    scored.sort(key=lambda pair: (-pair[0], str(pair[1])))

    return scored[0][1]


def choose_random(files: Sequence[Path], avoid: Path | None = None) -> Path | None:
    """A song at random, preferring not to repeat the last one.

    Args:
        files: The library to choose from.
        avoid: The song played last time, if any.

    Returns:
        The chosen file, or ``None`` for an empty library.
    """
    if not files:
        return None

    candidates = [path for path in files if path != avoid] or list(files)

    return random.choice(candidates)


def open_with_system_player(path: Path) -> None:
    """Hands a file to the OS's default application for its type.

    Deliberately not a bundled player: this uses whatever the machine
    already opens an .mp3 with, so there's no new dependency and no
    codec to ship.
    """
    if sys.platform.startswith("win"):
        # Windows-only, hence the guard above.
        os.startfile(path)  # type: ignore[attr-defined]
        return

    opener = "open" if sys.platform == "darwin" else "xdg-open"

    subprocess.Popen(
        [opener, str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class MusicTool(Tool):
    """Plays music from the user's folders, or YouTube as a fallback.

    Attributes:
        _folders: Folders to search for downloaded songs.
        _enabled: Whether playback happens at all.
        _player: Opens a local file. Injectable so tests never launch
            anything.
        _opener: Opens a URL. Same reason.
        _last_played: The last song started, so "play music" twice in
            a row doesn't play the same track.
    """

    def __init__(
        self,
        folders: Sequence[str | Path] | None = None,
        *,
        enabled: bool = True,
        player: Callable[[Path], None] | None = None,
        opener: Callable[[str], object] | None = None,
        search_url: str = YOUTUBE_SEARCH_URL,
    ) -> None:
        """Builds the tool.

        Args:
            folders: Folders to search. Defaults to ``~/Music`` and
                ``~/Downloads``, which covers where a downloaded song
                usually ends up.
            enabled: Whether playback happens at all.
            player: Opens a local file. Defaults to the system player.
            opener: Opens a URL. Defaults to the default browser.
            search_url: Where to search when a song isn't owned, with
                ``{query}`` where the search terms go.
        """
        self._folders = list(folders) if folders else list(DEFAULT_MUSIC_FOLDERS)
        self._enabled = enabled
        self._player = player or open_with_system_player
        self._opener = opener or webbrowser.open
        self._search_url = search_url
        self._last_played: Path | None = None

    @property
    def name(self) -> str:
        return "music"

    def execute(self, command: str = "") -> ToolResult:
        if not self._enabled:
            return ToolResult(
                success=False,
                message=(
                    "Music playback is disabled. Set music_enabled=true "
                    "in config/settings.json to turn it on."
                ),
            )

        request = parse_request(command or "")
        library = find_audio_files(self._folders)

        logger.info(
            "Music request %r against %d file(s) in %s.",
            request or "(any)",
            len(library),
            ", ".join(str(folder) for folder in self._folders),
        )

        if not request:
            chosen = choose_random(library, avoid=self._last_played)

            if chosen is None:
                return ToolResult(
                    success=False,
                    message=(
                        "I couldn't find any music in your music folders. "
                        "Name a song and I'll look it up on YouTube instead."
                    ),
                )

            return self._play(chosen, f"Playing {chosen.stem}.")

        match = match_song(request, library)

        if match is not None:
            return self._play(match, f"Playing {match.stem}.")

        return self._search(request)

    def _play(self, path: Path, message: str) -> ToolResult:
        """Starts a local file, remembering it as the last played."""
        try:
            self._player(path)
        except Exception as error:
            logger.warning("Could not play %s: %s", path, error)
            return ToolResult(
                success=False,
                message=f"I found {path.stem} but couldn't play it: {error}",
            )

        self._last_played = path
        return ToolResult(success=True, message=message)

    def _search(self, request: str) -> ToolResult:
        """Opens a web search for a song that isn't in the library."""
        url = self._search_url.format(query=quote_plus(request))

        try:
            self._opener(url)
        except Exception as error:
            logger.warning("Could not open %s: %s", url, error)
            return ToolResult(
                success=False,
                message=f"I don't have {request} in your library, and I couldn't open a browser to look it up: {error}",
            )

        return ToolResult(
            success=True,
            message=(
                f"I don't have {request} in your library, so I've opened "
                f"a YouTube search for it."
            ),
        )
