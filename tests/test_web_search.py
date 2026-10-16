"""Tests for web-search grounding.

The parsing, decision and formatting logic is pure and tested directly.
Nothing here touches the network: the client tests use small talk or the
disabled client, both of which return before any request is made.
"""

from __future__ import annotations

from src.modules.brain.context import ContextBuilder
from src.modules.conversation.history import ConversationHistory
from src.modules.identity.manager import IdentityManager
from src.modules.tools.knowledge.web_search import (
    WebPassage,
    WebSearchClient,
    build_search_query,
    format_grounding,
    looks_like_knowledge_question,
    parse_duckduckgo_html,
)

# A trimmed but structurally faithful capture of a DuckDuckGo results
# page (two results, with the redirect links and an inline <b> tag).
_DDG_HTML = '''
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.whitehouse.gov%2Fadministration%2Fdonald%2Dj%2Dtrump%2F&amp;rut=abc">President Donald J. Trump - The White House</a>
    </h2>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.whitehouse.gov%2F">President Trump built on his success in private life.</a>
  </div>
</div>
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FDonald_Trump&amp;rut=def">Donald Trump - Wikipedia</a>
    </h2>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FDonald_Trump">Donald John Trump (born June 14, 1946) is the <b>47th president</b> of the United States.</a>
  </div>
</div>
'''


# --- parsing -----------------------------------------------------------


def test_parse_extracts_titles_snippets_and_urls():
    passages = parse_duckduckgo_html(_DDG_HTML)

    assert len(passages) == 2
    assert passages[0].title == "President Donald J. Trump - The White House"
    assert passages[1].title == "Donald Trump - Wikipedia"


def test_parse_unwraps_redirect_urls():
    passages = parse_duckduckgo_html(_DDG_HTML)

    assert passages[0].url == (
        "https://www.whitehouse.gov/administration/donald-j-trump/"
    )
    assert passages[1].url == "https://en.wikipedia.org/wiki/Donald_Trump"


def test_parse_strips_inline_tags_from_snippets():
    passages = parse_duckduckgo_html(_DDG_HTML)

    assert "47th president" in passages[1].snippet
    assert "<b>" not in passages[1].snippet


def test_parse_returns_nothing_for_a_challenge_page():
    # What DuckDuckGo serves instead of results when it rate-limits.
    assert parse_duckduckgo_html("<html><body>challenge</body></html>") == []


def test_parse_handles_a_result_with_no_snippet():
    page = (
        '<a class="result__a" '
        'href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa">'
        "Only a title</a>"
    )
    passages = parse_duckduckgo_html(page)

    assert len(passages) == 1
    assert passages[0].snippet == ""
    assert passages[0].url == "https://example.com/a"


# --- deciding when to search -------------------------------------------


def test_questions_about_the_world_are_grounded():
    assert looks_like_knowledge_question("who is the president of the united states")
    assert looks_like_knowledge_question("what is the capital of australia")
    assert looks_like_knowledge_question("tell me about the solar system")
    assert looks_like_knowledge_question("is the earth flat?")


def test_small_talk_is_never_grounded():
    # These contain question words, so a naive check would search for them.
    assert not looks_like_knowledge_question("how are you")
    assert not looks_like_knowledge_question("what's up")
    assert not looks_like_knowledge_question("who are you")
    assert not looks_like_knowledge_question("thanks")


def test_single_word_messages_are_not_grounded():
    assert not looks_like_knowledge_question("hi")
    assert not looks_like_knowledge_question("ok")


# --- query building ----------------------------------------------------


def test_query_strips_the_wake_word_and_punctuation():
    assert (
        build_search_query("hey EON, who is the president of America?")
        == "who is the president of America"
    )
    assert (
        build_search_query("  what is the capital of France  ")
        == "what is the capital of France"
    )


# --- formatting --------------------------------------------------------


def test_format_grounding_is_empty_without_passages():
    assert format_grounding([]) == ""


def test_format_grounding_includes_title_snippet_and_source():
    text = format_grounding(
        [
            WebPassage(
                title="Donald Trump - Wikipedia",
                snippet="...is the 47th president of the United States.",
                url="https://en.wikipedia.org/wiki/Donald_Trump",
            )
        ]
    )

    assert "Web search results" in text
    assert "Donald Trump - Wikipedia" in text
    assert "47th president" in text
    assert "https://en.wikipedia.org/wiki/Donald_Trump" in text


# --- client behaviour (no network) -------------------------------------


def test_disabled_client_returns_nothing():
    client = WebSearchClient(enabled=False)

    assert client.grounding_for("who is the president of the united states") == []
    assert client.search("anything") == []


def test_client_skips_small_talk_without_searching():
    client = WebSearchClient()

    assert client.grounding_for("how are you") == []


# --- integration with the prompt ---------------------------------------


def test_build_injects_web_results_into_the_system_message():
    builder = ContextBuilder(identity=IdentityManager())

    messages = builder.build(
        history=ConversationHistory(),
        memories=[],
        knowledge=[
            WebPassage(
                title="Donald Trump - Wikipedia",
                snippet="...is the 47th president of the United States.",
                url="https://en.wikipedia.org/wiki/Donald_Trump",
            )
        ],
    )

    assert messages[0]["role"] == "system"
    content = messages[0]["content"]
    assert "Web search results" in content
    assert "https://en.wikipedia.org/wiki/Donald_Trump" in content


def test_build_without_knowledge_has_no_web_section():
    builder = ContextBuilder(identity=IdentityManager())

    messages = builder.build(history=ConversationHistory(), memories=[])

    assert "Web search results" not in messages[0]["content"]
