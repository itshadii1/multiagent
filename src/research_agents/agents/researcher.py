"""Researcher: answers one sub-question from live web search.

Many of these run in parallel, one per sub-question from the planner.

Sources are recorded from what the search tool actually returned, not from
the model's own "Sources:" list — a model can hallucinate a URL it never
retrieved, and the critic later needs ground truth to check claims against.
"""

from research_agents.llm import run_tool_loop
from research_agents.state import Finding, SubQuestion
from research_agents.tools.search import WEB_SEARCH_SCHEMA, web_search

SYSTEM_PROMPT = """You are a research agent. Answer the user's question using the web_search tool.

Rules:
- Search before answering. Never answer from memory alone.
- Run more than one search when the question has distinct parts.
- Ground every factual claim in a source you actually retrieved.
- Quote concrete figures and dates where the sources give them.
- If the sources do not settle the question, say so plainly instead of guessing.
- Answer in a few tight paragraphs. Another agent writes the final report; your
  job is accurate material, not prose."""


def _search_recording_sources(urls: list[str]):
    """web_search, wrapped to record every URL it hands back."""

    def tool(query: str, max_results: int = 5) -> str:
        results = web_search(query, max_results=max_results)
        if not results:
            return "No results found."
        for r in results:
            if r.url not in urls:
                urls.append(r.url)
        return "\n\n".join(
            f"[{i}] {r.title}\nURL: {r.url}\n{r.content}"
            for i, r in enumerate(results, start=1)
        )

    return tool


def research_sub_question(sub_question: SubQuestion) -> Finding:
    urls: list[str] = []
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": sub_question.question},
    ]
    answer = run_tool_loop(
        messages=messages,
        tool_schemas=[WEB_SEARCH_SCHEMA],
        tool_impls={"web_search": _search_recording_sources(urls)},
    )
    return Finding(
        sub_question_id=sub_question.id,
        question=sub_question.question,
        answer=answer,
        sources=urls,
    )


def research(question: str) -> str:
    """Single-shot entrypoint used by the M1 CLI path."""
    finding = research_sub_question(SubQuestion(id=1, question=question, rationale=""))
    sources = "\n".join(f"- {u}" for u in finding.sources)
    return f"{finding.answer}\n\nSources:\n{sources}"
