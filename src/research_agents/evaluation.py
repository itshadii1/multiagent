"""Quality checks on the finished report.

The critic decides whether to loop; these checks measure the result. Both
matter, but only this file produces a number you can put on a resume and
defend in an interview.

Two kinds, deliberately:

- **rule-based** (`check_citations_resolve`, `check_citation_coverage`) —
  deterministic, free, no key, and unfoolable. A citation either resolves to
  a retrieved URL or it does not.
- **LLM-as-judge** (`judge_coverage`) — for what rules cannot see, i.e.
  whether a sub-question was actually *answered*. It costs a call and it can
  be wrong, so it is reported alongside the rule checks, never instead of them.

The rule checks are the honest ones. Lead with them.
"""

import re

from research_agents.llm import complete_json
from research_agents.state import EvalResult, Finding, SubQuestion
from pydantic import BaseModel, Field

CITATION_RE = re.compile(r"\[(\d+)\]")


def _body(report: str) -> str:
    """The report minus the reference list we appended ourselves."""
    return report.split("## Sources")[0]


def check_citations_resolve(report: str, sources: list[str]) -> EvalResult:
    """Every [n] must point at a URL a researcher actually retrieved.

    This is the anti-hallucination check: a marker outside the registry range
    is the model inventing a source.
    """
    numbers = [int(n) for n in CITATION_RE.findall(_body(report))]
    if not numbers:
        return EvalResult(
            name="citations_resolve",
            passed=False,
            score=0.0,
            detail="The report cites nothing at all.",
        )

    bad = sorted({n for n in numbers if not 1 <= n <= len(sources)})
    score = (len(numbers) - sum(1 for n in numbers if n in bad)) / len(numbers)
    return EvalResult(
        name="citations_resolve",
        passed=not bad,
        score=score,
        detail=(
            f"All {len(numbers)} citations resolve to retrieved sources."
            if not bad
            else f"{len(bad)} citation(s) point outside the {len(sources)} retrieved sources: {bad}"
        ),
    )


def check_citation_coverage(report: str) -> EvalResult:
    """What fraction of substantive paragraphs carry a citation.

    A proxy, and worth naming as one: it counts paragraphs, not claims. A
    paragraph can be cited and still assert something its source never said —
    that is the critic's job, not a regex's.
    """
    paragraphs = [
        p
        for p in (block.strip() for block in _body(report).split("\n\n"))
        # Headings assert nothing, so requiring a citation on them is noise.
        if p and not p.startswith("#") and len(p) > 80
    ]
    if not paragraphs:
        return EvalResult(
            name="citation_coverage",
            passed=False,
            score=0.0,
            detail="No substantive paragraphs found.",
        )

    cited = sum(1 for p in paragraphs if CITATION_RE.search(p))
    score = cited / len(paragraphs)
    return EvalResult(
        name="citation_coverage",
        passed=score >= 0.8,
        score=score,
        detail=f"{cited}/{len(paragraphs)} substantive paragraphs carry a citation.",
    )


class _CoverageVerdict(BaseModel):
    answered_ids: list[int] = Field(description="Ids of sub-questions the report substantively answers.")
    missing: list[str] = Field(default_factory=list, description="Sub-questions left unanswered, quoted.")


def judge_coverage(
    sub_questions: list[SubQuestion],
    report: str,
) -> EvalResult:
    """LLM-as-judge: did the report answer every sub-question the planner set?

    Costs one call. Rule checks cannot do this one — "was this question
    answered" is a semantic judgement, not a pattern.
    """
    questions = "\n".join(f"{sq.id}. {sq.question}" for sq in sub_questions)
    verdict = complete_json(
        [
            {
                "role": "system",
                "content": (
                    "You check whether a report answers each of a list of questions. "
                    "A question counts as answered only if the report gives a substantive "
                    "answer to it. A report that explicitly says the answer could not be "
                    "established counts as answered — reporting a gap honestly is an answer. "
                    "Judge coverage only. Ignore style and length."
                ),
            },
            {"role": "user", "content": f"Questions:\n{questions}\n\n--- REPORT ---\n\n{report}"},
        ],
        _CoverageVerdict,
    )

    answered = {i for i in verdict.answered_ids if any(sq.id == i for sq in sub_questions)}
    score = len(answered) / len(sub_questions) if sub_questions else 0.0
    return EvalResult(
        name="sub_question_coverage",
        passed=score == 1.0,
        score=score,
        detail=(
            f"{len(answered)}/{len(sub_questions)} sub-questions answered."
            + (f" Missing: {'; '.join(verdict.missing)}" if verdict.missing else "")
        ),
    )


def evaluate(
    report: str,
    sources: list[str],
    sub_questions: list[SubQuestion],
    findings: list[Finding] | None = None,
    use_judge: bool = True,
) -> list[EvalResult]:
    """Run the checks. `use_judge=False` keeps it free and deterministic."""
    results = [
        check_citations_resolve(report, sources),
        check_citation_coverage(report),
    ]
    if use_judge and sub_questions:
        try:
            results.append(judge_coverage(sub_questions, report))
        except Exception as exc:
            # A judge that errors must not sink a finished report — the report
            # is the deliverable, the score is commentary on it.
            results.append(
                EvalResult(
                    name="sub_question_coverage",
                    passed=False,
                    score=0.0,
                    detail=f"Judge failed to run: {exc}",
                )
            )
    return results
