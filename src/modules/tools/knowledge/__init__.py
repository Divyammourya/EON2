"""Knowledge tools: web-search grounding for chat replies."""

from .web_search import (
    WebPassage,
    WebSearchClient,
    build_search_query,
    format_grounding,
    looks_like_knowledge_question,
    parse_duckduckgo_html,
)

__all__ = [
    "WebPassage",
    "WebSearchClient",
    "build_search_query",
    "format_grounding",
    "looks_like_knowledge_question",
    "parse_duckduckgo_html",
]
