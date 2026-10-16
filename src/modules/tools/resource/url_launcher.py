"""
URL Launcher.

Launches websites using the default browser.
"""

from __future__ import annotations

import webbrowser


class UrlLauncher:
    """
    Opens websites in the default browser.
    """

    def __init__(self) -> None:

        self._sites = {
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "github": "https://github.com",
            "chatgpt": "https://chat.openai.com",
            "gmail": "https://mail.google.com",
            "reddit": "https://www.reddit.com",
            "stackoverflow": "https://stackoverflow.com",
            "twitter": "https://twitter.com",
            "x": "https://x.com",
            "facebook": "https://www.facebook.com",
            "instagram": "https://www.instagram.com",
            "linkedin": "https://www.linkedin.com",
            "netflix": "https://www.netflix.com",
            "amazon": "https://www.amazon.com",
            "spotify": "https://open.spotify.com",
            "whatsapp": "https://web.whatsapp.com",
            "maps": "https://maps.google.com",
            "twitch": "https://www.twitch.tv",
            "discord": "https://discord.com/app",
            "wikipedia": "https://www.wikipedia.org",
            "claude": "https://claude.ai",
        }

    @property
    def known_names(self) -> set[str]:
        """
        Names of the well-known sites this launcher can open.
        """
        return set(self._sites.keys())

    def open(self, query: str) -> bool:

        key = query.strip().lower()

        url = self._sites.get(key)

        if url is None:
            return False

        webbrowser.open(url)

        return True
