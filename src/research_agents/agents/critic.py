"""Critic: reviews the draft and decides whether it goes back to the writer.

This is the reflection half of the system. The graph, not the critic, owns
when to stop looping (`max_revisions`) — a critic asked "is this perfect?"
will always find something, and an unbounded loop burns the free tier for
diminishing edits.

The critic judges the report *against the findings*, never against its own
knowledge: it has not searched, so anything it "knows" is unsourced, and a
critic that argues from memory would inject exactly the unsupported claims
it exists to remove.
"""

from research_agents.llm import complete_json
from research_agents.state import Critique, Finding, SubQuestion

SYSTEM_PROMPT = """You review a research report against the raw findings it was written from.

Judge ONLY against the findings given. You did not search. If the report states
something the findings do not support, that is a defect even if you believe it.

Reject ("revise") for any of:
- a factual claim with no citation, or one the cited finding does not support
- a sub-question the report leaves substantially unanswered
- a contradiction, either internal or against the findings
- a stated fact the findings actually hedge or dispute

Accept ("approve") when the report is supported and complete. Do not demand
polish: style, length, and tone are not defects. A well-sourced report that
honestly reports a gap is APPROVED — a gap the researchers left is not the
writer's defect. Only an unacknowledged gap is.

Be specific. "Section 2 claims India will hit 50GWh by 2030 with no citation;
finding 3 says the projection is disputed" is usable. "Needs more detail" is not.

List each issue separately in `issues`. Put the single most important change in
`guidance`. If you approve, leave `issues` empty."""


def critique_report(
    query: str,
    sub_questions: list[SubQuestion],
    findings: list[Finding],
    report: str,
) -> Critique:
    questions = "\n".join(f"{sq.id}. {sq.question}" for sq in sub_questions)
    material = "\n\n".join(
        f"### Finding {f.sub_question_id}: {f.question}\n{f.answer}"
        for f in sorted(findings, key=lambda f: f.sub_question_id)
    )
    return complete_json(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Research query: {query}\n\n"
                    f"Sub-questions that had to be answered:\n{questions}\n\n"
                    f"Findings the report must be supported by:\n\n{material}\n\n"
                    f"--- REPORT UNDER REVIEW ---\n\n{report}"
                ),
            },
        ],
        Critique,
    )
