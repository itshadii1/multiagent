"""Planner: turns one broad query into independent sub-questions.

Independence matters — researchers run in parallel and cannot see each
other's work, so a sub-question that depends on another's answer will
research badly.
"""

from research_agents.llm import complete_json
from research_agents.state import Plan

SYSTEM_PROMPT = """You break a research query into sub-questions for a team of researchers.

Rules:
- Produce 3 to 5 sub-questions. Fewer is better than padded.
- Each must be independently answerable: researchers work in parallel and cannot
  see each other's findings, so never write one that needs another's answer first.
- Together they should cover the main query without overlapping.
- Make each one concrete enough to search for. "Market size and growth rate of X
  since 2020" is searchable; "background on X" is not.
- Number them starting at 1."""


def plan(query: str) -> Plan:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Research query: {query}"},
    ]
    result = complete_json(messages, Plan)

    # Ids drive the join back to findings; renumber rather than trust the model.
    for i, sub_question in enumerate(result.sub_questions, start=1):
        sub_question.id = i
    return result
