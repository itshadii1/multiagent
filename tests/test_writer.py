"""Tests for the writer's citation machinery.

The prose is the model's; the numbering and the reference list are ours.
Only the second half is testable, and it's the half that makes a citation
trustworthy — so it's the half worth testing.
"""

from research_agents.agents.writer import (
    _render_references,
    _strip_model_reference_block,
    build_source_registry,
)
from research_agents.state import Finding


def _finding(id: int, sources: list[str]) -> Finding:
    return Finding(sub_question_id=id, question=f"q{id}", answer="a", sources=sources)


def test_registry_deduplicates_shared_sources():
    # Two researchers citing the same page must not produce two numbers for it.
    findings = [
        _finding(1, ["https://a.example", "https://b.example"]),
        _finding(2, ["https://b.example", "https://c.example"]),
    ]
    assert build_source_registry(findings) == [
        "https://a.example",
        "https://b.example",
        "https://c.example",
    ]


def test_registry_order_is_stable_regardless_of_completion_order():
    # Researchers finish in nondeterministic order; citation [1] must not
    # depend on which branch happened to return first.
    a = _finding(1, ["https://a.example"])
    b = _finding(2, ["https://b.example"])

    assert build_source_registry([a, b]) == build_source_registry([b, a])


def test_registry_is_empty_when_nothing_was_retrieved():
    assert build_source_registry([_finding(1, [])]) == []


def test_references_are_numbered_from_one():
    rendered = _render_references(["https://a.example", "https://b.example"])

    assert "1. https://a.example" in rendered
    assert "2. https://b.example" in rendered


def test_empty_model_reference_stub_is_stripped():
    # The exact shape observed on the first live run: a "References:" heading
    # followed by numbered stubs with nothing after them.
    body = "# Report\n\nClaim [1].\n\nReferences:\n[1] \n[2] \n[3]"
    assert _strip_model_reference_block(body) == "# Report\n\nClaim [1]."


def test_reference_heading_followed_by_prose_is_kept():
    # Real prose after the heading is the model's own words, not a stub list.
    body = "# Report\n\nClaim [1].\n\n## Sources\nThese findings draw on industry reports."
    assert _strip_model_reference_block(body) == body


def test_report_without_reference_block_is_untouched():
    body = "# Report\n\nClaim [1].\n\n## Gaps and limitations\n\nNone found."
    assert _strip_model_reference_block(body) == body


def test_reference_block_with_urls_and_prose_intro_is_stripped():
    # Second live shape: a prose intro, entries WITH urls, and the model's own
    # numbering — which contradicts the canonical list appended after it.
    body = (
        "# Report\n\nClaim [1].\n\n"
        "The reference list is appended as follows:\n"
        "[1] https://a.example\n"
        "[6] https://b.example\n"
        "[11] https://c.example"
    )
    assert _strip_model_reference_block(body) == "# Report\n\nClaim [1]."


def test_single_trailing_bracket_number_is_not_treated_as_a_list():
    # A report ending on a cited sentence like "…grew 40% [3]" must survive;
    # only a *run* of entry lines is a reference list.
    body = "# Report\n\nClaim [1].\n\n[3]"
    assert _strip_model_reference_block(body) == body
