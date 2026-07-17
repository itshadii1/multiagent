"""Web search tool, backed by Tavily.

Exposes both a plain Python function (callable from tests) and an
OpenAI-format tool schema (handed to the LLM).
"""

from functools import lru_cache

from pydantic import BaseModel, Field
from tavily import TavilyClient

from research_agents.config import get_settings


class SearchResult(BaseModel):
    title: str
    url: str
    content: str = Field(description="Snippet extracted by Tavily.")
    score: float = 0.0


@lru_cache
def _client() -> TavilyClient:
    return TavilyClient(api_key=get_settings().tavily_api_key)


def web_search(query: str, max_results: int = 5) -> list[SearchResult]:
    raw = _client().search(
        query=query,
        max_results=max_results,
        search_depth="basic",  # "advanced" costs 2 credits per call
    )
    return [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            content=r.get("content", ""),
            score=r.get("score", 0.0),
        )
        for r in raw.get("results", [])
    ]


WEB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the live web and return ranked results with titles, URLs, "
            "and content snippets. Use this for any fact you are not certain of, "
            "and for anything recent."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A focused search query. Prefer several narrow searches over one broad one.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "How many results to return (1-10).",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}


def run_web_search(query: str, max_results: int = 5) -> str:
    """Tool entrypoint: returns a string the LLM can read."""
    results = web_search(query, max_results=max_results)
    if not results:
        return "No results found."
    return "\n\n".join(
        f"[{i}] {r.title}\nURL: {r.url}\n{r.content}"
        for i, r in enumerate(results, start=1)
    )
