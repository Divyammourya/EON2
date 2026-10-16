from __future__ import annotations

from .base import CodingCommand


class SearchCommand(CodingCommand):

    def __init__(
        self,
        search_manager,
        query: str,
    ):
        self.search_manager = search_manager
        self.query = query

    def execute(self):

        matches = self.search_manager.search_text(
            self.query,
        )

        return {
            "query": self.query,
            "matches": [str(path) for path in matches],
            "match_count": len(matches),
        }
