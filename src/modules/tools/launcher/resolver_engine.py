"""
Application Resolver.

Resolves a user query into the best matching application.
"""

from __future__ import annotations

from src.modules.tools.launcher.models import Application
from src.modules.tools.launcher.registry import ApplicationRegistry


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

        # Reverse contains
        elif name in query:
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
