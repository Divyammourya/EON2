"""Web-search grounding for EON's chat replies.

Why this exists
---------------
EON runs a small local model with no internet access. Asked about the
world — "who is the president of the United States" — it answers from its
training data and is confidently wrong or out of date. This module lets
EON look the question up first and hand the model real, current text to
answer from, instead of guessing.

How it works
------------
``WebSearchClient.grounding_for(text)`` decides whether the message is the
kind of question that needs the web (see ``looks_like_knowledge_question``),
runs one search, and returns the top passages. ``Brain`` passes those to
``ContextBuilder.build``, which drops them into the system prompt as a
"Web search results" section, so the model answers from them.

The primary backend is DuckDuckGo's HTML endpoint: free, no API key, no
account, and its snippets usually *state* the answer rather than merely
describing the topic. It is a *scrape*, not a documented API, so the
markup can change and break the parser — ``parse_duckduckgo_html`` is
therefore pure and unit-tested against a captured page.

DuckDuckGo rate-limits bursts (it answers ``202`` with a challenge page,
not results), which would otherwise mean silently answering with no
grounding at all. So when it yields nothing, the client falls back to
Wikipedia's documented JSON API. That is the more stable source, but its
article intros describe *topics* — they don't always state the live
answer — which is why it is the fallback rather than the primary.

Every failure path returns no passages rather than raising, so a search
outage degrades to EON's normal behaviour.

Requires: Python 3.12+
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from src.core.logger import get_logger

logger = get_logger("WebSearch")

_SEARCH_URL = "https://html.duckduckgo.com/html/"
_WIKI_API = "https://en.wikipedia.org/w/api.php"
_WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"

# Wikipedia intros can be long; cap what we hand the model.
_MAX_SNIPPET_CHARS = 500

# DuckDuckGo's HTML endpoint serves an anti-bot page unless the request
# looks like an ordinary browser.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Wikipedia's API requires a descriptive User-Agent identifying the app and
# a contact, and rejects a generic browser one with 403 (unlike the search
# endpoint above, which requires the opposite).
_WIKI_HEADERS = {
    "User-Agent": "EON/0.1 (personal AI assistant; +https://github.com/Divyammourya/EON2)",
    "Accept": "application/json",
}

_TITLE_RE = re.compile(
    r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.S | re.I,
)
_SNIPPET_RE = re.compile(
    r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
    re.S | re.I,
)
_TAGS_RE = re.compile(r"<[^>]+>")

_QUESTION_STARTERS = (
    "who",
    "what",
    "when",
    "where",
    "which",
    "why",
    "how",
    "whose",
    "whom",
)

_KNOWLEDGE_PREFIXES = (
    "tell me about",
    "tell me the",
    "explain",
    "describe",
    "history of",
    "what do you know about",
    "give me information about",
)

# Small talk that happens to contain a question word ("how are you",
# "what's up") and must not trigger a pointless search.
_SMALL_TALK = (
    "how are you",
    "how's it going",
    "hows it going",
    "what's up",
    "whats up",
    "who are you",
    "what are you",
    "what is your name",
    "what's your name",
    "whats your name",
    "who made you",
    "who created you",
    "who built you",
    "tell me about yourself",
    "good morning",
    "good evening",
    "good night",
    "thank you",
    "thanks",
)


# Words that mean "I am asking about now". An encyclopedia cannot answer
# these: its article intros describe *topics* and carry no date, so a
# question about something recent gets answered with whatever old event
# happens to share a word with it.
_RECENCY_WORDS = (
    "recent",
    "recently",
    "latest",
    "today",
    "tonight",
    "yesterday",
    "this week",
    "this month",
    "this year",
    "right now",
    "currently",
    "at the moment",
    "news",
    "breaking",
    "just happened",
    "going on",
)

# Stripped before a keyword search. Includes the question words, the
# polite scaffolding ("can you tell me about"), and the recency words —
# none of them name anything a search index can match on.
_STOP_WORDS = frozenset(
    {
        "a", "about", "after", "all", "am", "an", "and", "any", "are", "as",
        "at", "be", "been", "being", "but", "by", "can", "could", "did", "do",
        "does", "doing", "for", "from", "get", "give", "had", "has", "have",
        "he", "her", "here", "him", "his", "how", "i", "if", "in", "into",
        "is", "it", "its", "just", "know", "let", "like", "me", "more", "most",
        "my", "no", "not", "of", "on", "one", "only", "or", "other", "our",
        "out", "over", "please", "should", "so", "some", "such", "tell", "than",
        "that", "the", "their", "them", "then", "there", "these", "they",
        "this", "those", "to", "too", "up", "us", "very", "was", "we", "were",
        "what", "when", "where", "which", "while", "who", "whom", "whose",
        "why", "will", "with", "would", "you", "your",
    }
    | set(_RECENCY_WORDS)
)


def _keywords(text: str) -> set[str]:
    """The content words in a question.

    Everything short, common, or part of the question's scaffolding is
    dropped, leaving the words that name something a page could be
    *about*: "can you tell me about the protest that is happened
    recently in france?" becomes {"protest", "happened", "france"}.
    """
    words = re.findall(r"[a-z0-9]+", text.lower())

    return {
        word for word in words if len(word) > 2 and word not in _STOP_WORDS
    }


def _keyword_query(text: str) -> str:
    """The question as a search *index* wants it.

    DuckDuckGo takes natural language, which is why
    ``build_search_query`` leaves the sentence alone. Wikipedia does not:
    it is a keyword index, and handed the whole sentence it answered a
    question about protests in France with "Tommy (The Who album)" and
    "Giovanni's Room".
    """
    words = sorted(_keywords(text))

    return " ".join(words) if words else text.strip()


def _asks_for_recent(text: str) -> bool:
    """Whether the question is about *now* rather than about a topic."""
    lowered = text.lower()

    return any(word in lowered for word in _RECENCY_WORDS)


def _is_wikipedia(passage: WebPassage) -> bool:
    """Whether a passage came from the fallback rather than a search."""
    return "wikipedia.org" in passage.url


def _relevant(passage: WebPassage, keywords: set[str]) -> bool:
    """Whether a passage touches the question at all.

    Deliberately loose — a real answer often shares only one word with
    the question — but not *no* words, which is what a page matched on
    the word "the" looks like.
    """
    if not keywords:
        return True

    return bool(_keywords(f"{passage.title} {passage.snippet}") & keywords)


@dataclass(slots=True)
class WebPassage:
    """One search result: a title, a snippet, and the source URL."""

    title: str
    snippet: str
    url: str


def _strip_tags(fragment: str) -> str:
    """Removes HTML tags and unescapes entities from a fragment."""
    return html.unescape(_TAGS_RE.sub("", fragment)).strip()


def _real_url(href: str) -> str:
    """Unwraps DuckDuckGo's redirect into the destination URL.

    Result links point at ``//duckduckgo.com/l/?uddg=<encoded>``; the
    actual destination is the ``uddg`` parameter.
    """
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    target = parse_qs(urlparse(href).query).get("uddg")
    if target:
        return unquote(target[0])
    return href


def parse_duckduckgo_html(page: str) -> list[WebPassage]:
    """Extracts results from a DuckDuckGo HTML page.

    Pure, so it can be tested against a captured page with no network.
    Titles and snippets are paired positionally — the Nth snippet belongs
    to the Nth result link, which is how the markup orders them.

    Args:
        page: The raw HTML of a DuckDuckGo results page.

    Returns:
        The passages found, in page order. Empty if nothing matched,
        which is also what a markup change would look like.
    """
    titles = _TITLE_RE.findall(page)
    snippets = _SNIPPET_RE.findall(page)

    passages: list[WebPassage] = []

    for index, (href, raw_title) in enumerate(titles):
        title = _strip_tags(raw_title)
        if not title:
            continue
        snippet = _strip_tags(snippets[index]) if index < len(snippets) else ""
        passages.append(
            WebPassage(title=title, snippet=snippet, url=_real_url(href))
        )

    return passages


def looks_like_knowledge_question(text: str) -> bool:
    """Decides whether ``text`` is a question about the world.

    Only CHAT messages reach this — commands and tool requests are routed
    away earlier — so the job here is mainly to *exclude* small talk,
    which would otherwise trigger a pointless search ("how are you"
    contains "how").

    Being generous is deliberate: a needless search costs a little
    latency, while a missed one means the model answers from memory and
    is confidently wrong, which is the bug this exists to fix.
    """
    stripped = text.strip().lower()
    if len(stripped.split()) < 2:
        return False

    if any(phrase in stripped for phrase in _SMALL_TALK):
        return False

    if stripped.split()[0].strip(",.!?;:") in _QUESTION_STARTERS:
        return True

    if stripped.startswith(_KNOWLEDGE_PREFIXES):
        return True

    return stripped.endswith("?")


def build_search_query(text: str) -> str:
    """Turns a spoken question into a search query.

    Strips the wake word and surrounding punctuation and otherwise leaves
    the question intact — DuckDuckGo handles natural-language queries
    well, and rewriting them risks losing the point of the question.
    """
    query = re.sub(r"^\s*(hey\s+)?eon[,:\s]+", "", text.strip(), flags=re.I)
    return query.strip(" ?.!,")


def _wikipedia_passages(
    query: str,
    limit: int,
    timeout: float,
) -> list[WebPassage]:
    """Fallback source: Wikipedia's documented JSON API.

    Used only when DuckDuckGo returns nothing. One search call, then a
    summary call per hit. Any failure skips that hit rather than raising.
    """
    try:
        found = httpx.get(
            _WIKI_API,
            params={
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "srlimit": max(1, limit),
            },
            headers=_WIKI_HEADERS,
            timeout=timeout,
        )
        found.raise_for_status()
        titles = [
            hit["title"]
            for hit in found.json().get("query", {}).get("search", [])
        ]
    except (httpx.HTTPError, ValueError, KeyError):
        return []

    passages: list[WebPassage] = []

    for title in titles:
        try:
            page = httpx.get(
                _WIKI_SUMMARY + title.replace(" ", "_"),
                headers=_WIKI_HEADERS,
                timeout=timeout,
            )
            page.raise_for_status()
            data = page.json()
        except (httpx.HTTPError, ValueError):
            continue

        extract = (data.get("extract") or "").strip()
        if not extract:
            continue

        passages.append(
            WebPassage(
                title=title,
                snippet=extract[:_MAX_SNIPPET_CHARS],
                url=(
                    data.get("content_urls", {})
                    .get("desktop", {})
                    .get("page", "")
                ),
            )
        )

    return passages


def format_grounding(passages: list[WebPassage]) -> str:
    """Renders passages as a system-prompt section, or "" if none."""
    if not passages:
        return ""

    lines = [
        "\n\nWeb search results",
        "-------------------",
        "Live results for the user's question. Treat these as your source of",
        "truth, prefer them over anything you remember, and name the source",
        "when you use it. If they do not answer the question, say so rather",
        "than guessing.\n",
    ]

    for index, passage in enumerate(passages, start=1):
        lines.append(f"{index}. {passage.title}")
        if passage.snippet:
            lines.append(f"   {passage.snippet}")
        if passage.url:
            lines.append(f"   Source: {passage.url}")

    return "\n".join(lines) + "\n"


class WebSearchClient:
    """Fetches web passages to ground a chat reply.

    Attributes:
        _enabled: Whether grounding is on at all. When off, every method
            returns nothing and no network call is made.
        _max_results: How many passages to keep.
        _timeout: Per-request timeout, in seconds.
    """

    def __init__(
        self,
        enabled: bool = True,
        max_results: int = 3,
        timeout_seconds: float = 8.0,
    ) -> None:
        self._enabled = enabled
        self._max_results = max(1, max_results)
        self._timeout = timeout_seconds

    @property
    def enabled(self) -> bool:
        """Whether web grounding is switched on."""
        return self._enabled

    def search(self, query: str) -> list[WebPassage]:
        """Runs one search and returns the top passages.

        Never raises: any failure — offline, timeout, blocked, or a
        markup change — is logged and returns an empty list, so a search
        outage degrades to EON's own answer instead of breaking the turn.
        """
        if not self._enabled or not query.strip():
            return []

        passages: list[WebPassage] = []

        try:
            response = httpx.get(
                _SEARCH_URL,
                params={"q": query},
                headers=_HEADERS,
                timeout=self._timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            passages = parse_duckduckgo_html(response.text)[: self._max_results]
        except httpx.HTTPError as error:
            logger.warning("DuckDuckGo search failed (%s); trying fallback.", error)

        if passages:
            return self._keep_relevant(passages, query)

        # Either DuckDuckGo errored, rate-limited us (a 202 challenge page
        # parses to nothing), or genuinely had no results. Try the stable
        # API before giving up on grounding this turn. It is a keyword
        # index, so it gets keywords rather than the sentence.
        logger.info("No DuckDuckGo results; trying Wikipedia fallback.")

        return self._keep_relevant(
            _wikipedia_passages(
                _keyword_query(query), self._max_results, self._timeout
            ),
            query,
        )

    @staticmethod
    def _keep_relevant(
        passages: list[WebPassage],
        query: str,
    ) -> list[WebPassage]:
        """Drops passages that share nothing with the question.

        Retrieval is generous; this is what stops a page matched on an
        incidental word from being handed to the model as *evidence*,
        where it reads exactly like a real answer.

        Args:
            passages: What the backend returned.
            query: The query they were returned for.

        Returns:
            Only the passages that touch the question.
        """
        keywords = _keywords(query)

        relevant = [p for p in passages if _relevant(p, keywords)]

        if passages and not relevant:
            logger.info(
                "Dropped %d passage(s) that shared nothing with the question.",
                len(passages),
            )

        return relevant

    def grounding_for(self, text: str) -> list[WebPassage]:
        """Returns passages worth grounding ``text`` with, else an empty list.

        The last check is the important one. A question about something
        *recent* cannot be answered by an encyclopedia: Wikipedia's
        intros describe topics and are undated, so "the protest that
        happened recently in France" came back as the Yellow Vests
        protests of 2018-2020 and was stated as though it were current.
        The verification pass would not have caught that either — the
        passage genuinely does support the sentence; it is simply the
        wrong passage.

        So if the search engine had nothing and Wikipedia was the only
        source, and the question was about now, EON grounds on nothing
        and says it could not find anything recent. That is a worse
        answer and a better one.

        Args:
            text: The user's message.

        Returns:
            Passages to ground with, or an empty list.
        """
        if not self._enabled or not looks_like_knowledge_question(text):
            return []

        passages = self.search(build_search_query(text))

        if (
            passages
            and _asks_for_recent(text)
            and all(_is_wikipedia(p) for p in passages)
        ):
            logger.info(
                "Only Wikipedia answered a question about something "
                "recent; not grounding."
            )
            return []

        return passages
