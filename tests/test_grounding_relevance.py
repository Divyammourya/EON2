"""What EON is willing to treat as evidence.

This is the bug that came out of a real run:

    You: can you tell me about the protest that is happened recently in france?
    [Web] 3 result(s) for '...'
    EON: The yellow vest movement refers to those series of protests in
         France that began on 17 November 2018 and ended on 28 June 2020.

Three things went wrong at once, and each has a test here:

    1. DuckDuckGo rate-limited the request (a 202 challenge page), so the
       Wikipedia fallback ran — and was handed the whole sentence.
    2. Wikipedia is a *keyword* index, so it answered a question about
       protests in France with "Tommy (The Who album)" and "Giovanni's
       Room".
    3. Nothing checked whether any of it touched the question, so all
       three became "evidence" and the model picked the one that looked
       like an answer.

Note what the verification pass does *not* fix here: the Yellow Vests
passage genuinely does support that sentence. The sentence is true. It is
simply the answer to a different question, from six years earlier, offered
to someone who asked what was happening now. Catching that is retrieval's
job, not verification's.
"""

from __future__ import annotations

from src.modules.tools.knowledge.web_search import (
    WebPassage,
    WebSearchClient,
    _asks_for_recent,
    _is_wikipedia,
    _keyword_query,
    _keywords,
    _relevant,
)

# The exact question from the run.
_QUESTION = "can you tell me about the protest that is happened recently in france?"

# The exact three pages the fallback returned for it.
_FRANCE_TRIO = [
    WebPassage(
        title="Yellow vests protests",
        snippet="The yellow vests movement refers to a series of protests in France.",
        url="https://en.wikipedia.org/wiki/Yellow_vests_protests",
    ),
    WebPassage(
        title="Giovanni's Room",
        snippet="A novel by James Baldwin.",
        url="https://en.wikipedia.org/wiki/Giovanni's_Room",
    ),
    WebPassage(
        title="Tommy (The Who album)",
        snippet="A rock opera by The Who.",
        url="https://en.wikipedia.org/wiki/Tommy_(The_Who_album)",
    ),
]


# --- 1. the query is reduced to words a keyword index can use -------------


def test_the_scaffolding_is_stripped_out():
    assert _keywords(_QUESTION) == {"france", "happened", "protest"}


def test_the_recency_word_is_stripped_too():
    """An index cannot match on "recently" — and leaving it in is what
    invited an undated 2018 article to answer a question about now."""
    assert "recently" not in _keywords(_QUESTION)


def test_the_wikipedia_query_is_keywords_not_a_sentence():
    assert _keyword_query(_QUESTION) == "france happened protest"


def test_a_question_with_no_content_words_falls_back_to_itself():
    assert _keyword_query("what is it?") == "what is it?"


# --- 2. a question about "now" is recognised as one -----------------------


def test_a_recency_question_is_recognised():
    assert _asks_for_recent(_QUESTION)
    assert _asks_for_recent("what is the latest on the strike?")
    assert _asks_for_recent("what's in the news today")


def test_an_ordinary_topic_question_is_not():
    assert not _asks_for_recent("what is the capital of france")
    assert not _asks_for_recent("who wrote giovanni's room")


# --- 3. pages that share nothing with the question are not evidence -------


def test_the_two_pages_that_shared_nothing_are_dropped():
    """The literal bug: "Tommy (The Who album)" is not evidence about
    protests in France, and reading it as such is how the model got a
    wrong answer out of a right-looking prompt."""
    keywords = _keywords(_QUESTION)

    assert not _relevant(_FRANCE_TRIO[1], keywords)  # Giovanni's Room
    assert not _relevant(_FRANCE_TRIO[2], keywords)  # Tommy


def test_a_page_that_touches_the_question_survives_the_gate():
    """Loose on purpose: one shared word is enough, because a real answer
    often shares only one."""
    assert _relevant(_FRANCE_TRIO[0], _keywords(_QUESTION))


def test_wikipedia_is_recognised_by_its_url():
    assert _is_wikipedia(_FRANCE_TRIO[0])
    assert not _is_wikipedia(
        WebPassage(title="x", snippet="y", url="https://example.org/x")
    )


# --- 4. the whole path, as the Brain sees it ------------------------------


class _StubSearch(WebSearchClient):
    """Returns a fixed set of passages, so the rule can be tested alone."""

    def __init__(self, passages: list[WebPassage]) -> None:
        super().__init__(enabled=True)
        self.passages = passages
        self.queries: list[str] = []

    def search(self, query: str) -> list[WebPassage]:
        self.queries.append(query)
        return list(self.passages)


def test_a_recent_question_answered_only_by_wikipedia_is_not_grounded():
    """The fix. Better to answer badly and honestly than to be handed a
    six-year-old protest as though it were this week's."""
    client = _StubSearch(_FRANCE_TRIO)

    assert client.grounding_for(_QUESTION) == []


def test_a_recent_question_answered_by_a_real_search_is_kept():
    """The rule is about Wikipedia's inability to answer "now", not about
    recency questions as such — a search engine's fresh snippets are
    exactly what those questions need."""
    fresh = [
        WebPassage(
            title="Protests in France",
            snippet="Protests continued in France this week.",
            url="https://news.example.org/france-protests",
        )
    ]
    client = _StubSearch(fresh)

    assert client.grounding_for(_QUESTION) == fresh


def test_an_ordinary_question_can_still_use_wikipedia():
    client = _StubSearch(_FRANCE_TRIO)

    assert client.grounding_for("what is the capital of france") == _FRANCE_TRIO


def test_grounding_is_still_skipped_for_small_talk():
    """The older rule, unchanged: "how are you" must not search."""
    client = _StubSearch(_FRANCE_TRIO)

    assert client.grounding_for("how are you") == []
    assert client.queries == [], "small talk must not reach the search"
