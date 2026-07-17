"""Writer: assembles findings into a cited report.

Citations are handled as a split of responsibility, deliberately:

- the model writes prose containing `[n]` markers,
- *we* render the reference list from `build_source_registry`, whose URLs
  come from what the search tool actually returned.

So the model chooses which source supports a claim, but cannot invent the
source itself — the worst it can do is mis-number, which `evaluation.py`
then catches. Letting the model emit its own URL list is how citation
hallucination gets into a report.
"""

from research_agents.llm import complete
from research_agents.state import Critique, Finding

SYSTEM_PROMPT = """You write research reports from material gathered by other agents.

Rules:
- Use ONLY the findings given. Add no fact from memory, however sure you are.
- Cite with bracketed numbers, e.g. [2], matching the source numbers on each
  finding. Every factual claim needs one. Cite only numbers you were given.
- Never write a URL or a "Sources" section. The citation numbers are enough;
  the reference list is appended for you.
- Where findings disagree, say so and cite both rather than silently picking one.
- Where the research left a gap, state the gap plainly. Do not paper over it.

Structure:
# <title>
A short summary paragraph — the answer to the query, for someone who reads
nothing else.
## <thematic section>
One section per theme. Organize by theme, not by sub-question: sub-questions
are how the work was divided, not how a reader thinks.
## Gaps and limitations
What the research could not establish.

Markdown. Tight and concrete. Prefer figures and dates over adjectives."""


def build_source_registry(findings: list[Finding]) -> list[str]:
    """Every unique URL the researchers actually retrieved, in stable order.

    The index into this list (1-based) is the citation number, so ordering
    must not depend on set iteration or parallel completion order.
    """
    urls: list[str] = []
    for finding in sorted(findings, key=lambda f: f.sub_question_id):
        for url in finding.sources:
            if url not in urls:
                urls.append(url)
    return urls


def _render_findings(findings: list[Finding], sources: list[str]) -> str:
    blocks = []
    for finding in sorted(findings, key=lambda f: f.sub_question_id):
        numbers = ", ".join(f"[{sources.index(u) + 1}]" for u in finding.sources)
        blocks.append(
            f"### Sub-question {finding.sub_question_id}: {finding.question}\n"
            f"Findings: {finding.answer}\n"
            f"Cite these as: {numbers or '(no sources retrieved — do not cite)'}"
        )
    return "\n\n".join(blocks)


def _render_references(sources: list[str]) -> str:
    lines = "\n".join(f"{i}. {url}" for i, url in enumerate(sources, start=1))
    return f"## Sources\n\n{lines}"


def write_report(
    query: str,
    findings: list[Finding],
    sources: list[str],
    critique: Critique | None = None,
) -> str:
    """Draft the report, or redraft it against a critique on a retry pass."""
    user_content = (
        f"Research query: {query}\n\n"
        f"Material gathered:\n\n{_render_findings(findings, sources)}"
    )

    # On a retry the critique is the whole point of the pass — make the model
    # fix named defects rather than reword the draft it already produced.
    if critique is not None and critique.issues:
        issues = "\n".join(f"- {issue}" for issue in critique.issues)
        user_content += (
            "\n\nA reviewer rejected your previous draft. Rewrite it in full, "
            f"fixing each issue:\n{issues}\n\nReviewer guidance: {critique.guidance}"
        )

    body = complete(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
    )
    return f"{body.strip()}\n\n{_render_references(sources)}"
