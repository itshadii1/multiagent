"""Tests for the rule-based quality checks.

These need no keys and no network — that's the point of them being rules.
The LLM judge is deliberately untested here: asserting on a model's judgement
would be testing the model, not the code.
"""

from research_agents.evaluation import check_citation_coverage, check_citations_resolve

SOURCES = ["https://a.example", "https://b.example"]

PARA = (
    "India's battery cell capacity reached 20 GWh in 2024, up from 3 GWh in 2021, "
    "with three gigafactories accounting for most of the additions."
)


def test_citations_resolve_when_in_range():
    report = f"# R\n\n{PARA} [1] And more [2].\n\n## Sources\n\n1. x\n2. y"
    result = check_citations_resolve(report, SOURCES)

    assert result.passed
    assert result.score == 1.0


def test_citation_out_of_range_is_caught():
    # [7] with two sources retrieved = an invented citation, the exact failure
    # the source registry exists to make detectable.
    report = f"# R\n\n{PARA} [1] and also [7].\n\n## Sources\n\n1. x\n2. y"
    result = check_citations_resolve(report, SOURCES)

    assert not result.passed
    assert result.score == 0.5
    assert "7" in result.detail


def test_uncited_report_fails():
    report = f"# R\n\n{PARA}\n\n## Sources\n\n1. x"
    assert not check_citations_resolve(report, SOURCES).passed


def test_reference_list_is_not_scanned_for_citations():
    # The appended "## Sources" block is ours, not the model's claim surface;
    # counting it would inflate every score.
    report = f"# R\n\n{PARA} [1]\n\n## Sources\n\n1. [9] https://a.example"
    result = check_citations_resolve(report, SOURCES)

    assert result.passed


def test_citation_coverage_counts_substantive_paragraphs_only():
    report = f"# Title\n\n## Section\n\n{PARA} [1]\n\n{PARA} [2]\n\n## Sources\n\n1. x"
    result = check_citation_coverage(report)

    assert result.passed
    assert result.score == 1.0


def test_citation_coverage_flags_uncited_paragraph():
    report = f"# Title\n\n{PARA} [1]\n\n{PARA}\n\n## Sources\n\n1. x"
    result = check_citation_coverage(report)

    assert not result.passed
    assert result.score == 0.5


def test_heading_glued_to_paragraph_is_still_scored():
    # Models often write "## Heading\ntext" with no blank line; the paragraph
    # must still count. Observed live: whole sections silently skipped.
    report = f"# Title\n\n## Section A\n{PARA} [1]\n\n## Section B\n{PARA}\n\n## Sources\n\n1. x"
    result = check_citation_coverage(report)

    assert result.score == 0.5  # both counted, one cited — not 1/1
