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

import re

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
        # Number AND url, paired. Observed live: given bare numbers, the model
        # invented its own sequential numbering, so its in-text [6] pointed at
        # a different entry than registry #6 — a mis-mapping citations_resolve
        # cannot catch, since the number is in range. Showing which URL each
        # number *is* anchors the mapping.
        cites = "\n".join(
            f"  [{sources.index(u) + 1}] = {u}" for u in finding.sources
        )
        blocks.append(
            f"### Sub-question {finding.sub_question_id}: {finding.question}\n"
            f"Findings: {finding.answer}\n"
            f"Cite this finding's claims with these numbers:\n"
            f"{cites or '  (no sources retrieved — do not cite)'}"
        )
    return "\n\n".join(blocks)


def _render_references(sources: list[str]) -> str:
    lines = "\n".join(f"{i}. {url}" for i, url in enumerate(sources, start=1))
    return f"## Sources\n\n{lines}"


# An entry line: "[3]", "3.", "- [3] https://…", "[3] https://…" — a citation
# number, optionally followed by a URL, and nothing else.
_REF_ENTRY = re.compile(r"^\s*[-*]?\s*\[?\d+\]?[.):]?\s*(https?://\S+)?\s*$")
# A line that introduces such a list: "References:", "## Sources", or prose
# like "The reference list is appended as follows:".
_REFS_INTRO = re.compile(
    r"(references|sources|citations|bibliography|reference list)", re.I
)


def _strip_model_reference_block(body: str) -> str:
    """Drop a reference list the model wrote despite being told not to.

    Prompting against this failed twice, in two shapes, both observed live:
    a `References:` heading over empty stubs (`[1]`, `[2]`, …), and a prose
    intro ("The reference list is appended as follows:") over entries with
    URLs — the second being actively dangerous, because the model renumbers
    freely and its list contradicts the canonical one we append.

    So: enforce in code. Take the trailing run of entry-shaped lines (two or
    more, so a report legitimately ending in a bracketed number survives),
    plus the line introducing them if it reads like one.
    """
    lines = body.rstrip().split("\n")

    i = len(lines)
    while i > 0 and (not lines[i - 1].strip() or _REF_ENTRY.match(lines[i - 1])):
        i -= 1
    entry_count = sum(1 for ln in lines[i:] if ln.strip())
    if entry_count < 2:
        return body.rstrip()

    intro = lines[i - 1].strip() if i > 0 else ""
    if _REFS_INTRO.search(intro) and (intro.endswith(":") or intro.startswith("#")):
        i -= 1
    return "\n".join(lines[:i]).rstrip()


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
    body = _strip_model_reference_block(body.strip())
    return f"{body}\n\n{_render_references(sources)}"
