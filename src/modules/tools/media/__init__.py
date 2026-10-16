"""EON's media tools package."""

from __future__ import annotations

from src.modules.tools.media.music import (
    AUDIO_EXTENSIONS,
    DEFAULT_MUSIC_FOLDERS,
    MusicTool,
    choose_random,
    find_audio_files,
    match_song,
    parse_request,
)

__all__ = [
    "AUDIO_EXTENSIONS",
    "DEFAULT_MUSIC_FOLDERS",
    "MusicTool",
    "choose_random",
    "find_audio_files",
    "match_song",
    "parse_request",
]
