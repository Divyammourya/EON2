"""
Application Resolver.

Resolves a user query into the best matching application.
"""

from __future__ import annotations

import re

from src.modules.tools.launcher.models import Application
from src.modules.tools.launcher.registry import ApplicationRegistry

# The shortest app name the "query contains the name" rule will match
# on. Below this, a name is short enough to appear inside an unrelated
# word — "od" inside "coding" — and the rule starts inventing matches.
_MIN_REVERSE_CONTAINS_LENGTH = 3


class ApplicationResolver:

    def __init__(self, registry: ApplicationRegistry) -> None:
        self.registry = registry

    def _score(self, query: str, app: Application) -> int:
        """
        Returns a relevance score.
        """

        query = query.lower().strip()
        name = app.name.lower()

        score = 0

        # Exact match
        if query == name:
            score += 100

        # Starts with
        elif name.startswith(query):
            score += 90

        # Contains
        elif query in name:
            score += 70

        # Reverse contains — the query has extra words around the app's
        # name ("open the notepad app"). This branch needs a word
        # boundary and a minimum length, or a short app name matches
        # almost anything: a registry entry called "od" is a substring
        # of "coding", so "coding workspace" scored 60 for it and won,
        # and EON launched a two-letter application instead of the thing
        # that was asked for.
        elif len(name) >= _MIN_REVERSE_CONTAINS_LENGTH and re.search(
            rf"\b{re.escape(name)}\b", query
        ):
            score += 60

        # Word overlap
        query_words = set(query.split())
        name_words = set(name.split())

        score += len(query_words & name_words) * 15

        # Alias match
        for alias in app.aliases:

            alias = alias.lower()

            if alias == query:
                score += 95

            elif query in alias:
                score += 75

        return score

    def resolve(self, query: str) -> Application | None:

        best_app = None
        best_score = 0

        for app in self.registry:

            score = self._score(query, app)

            if score > best_score:
                best_score = score
                best_app = app

        return best_app
