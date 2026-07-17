"""Tests for the writer's citation machinery.

The prose is the model's; the numbering and the reference list are ours.
Only the second half is testable, and it's the half that makes a citation
trustworthy — so it's the half worth testing.
"""

from research_agents.agents.writer import _render_references, build_source_registry
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
