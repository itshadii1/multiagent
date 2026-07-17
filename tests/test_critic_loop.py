"""Tests for the reflection loop — the behavior that distinguishes this
system from a linear chain.

Agents are faked, so what's under test is the routing: does a rejection
actually send the report back, does the writer see the critique, and does
the loop terminate when a stubborn critic never approves.
"""

import pytest

from research_agents import graph as graph_module
from research_agents.graph import build_graph, route_after_critic
from research_agents.state import Critique, Finding, Plan, SubQuestion


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Fakes planner/researcher/writer and records every writer call."""
    writer_calls: list[Critique | None] = []

    monkeypatch.setattr(
        graph_module,
        "plan",
        lambda query: Plan(sub_questions=[SubQuestion(id=1, question="q1", rationale="r")]),
    )
    monkeypatch.setattr(
        graph_module,
        "research_sub_question",
        lambda sq: Finding(
            sub_question_id=sq.id,
            question=sq.question,
            answer="a",
            sources=["https://example.com/1"],
        ),
    )

    def fake_write(query, findings, sources, critique=None):
        writer_calls.append(critique)
        return f"# Report\n\nBody [1].\n\n## Sources\n\n1. {sources[0]}"

    monkeypatch.setattr(graph_module, "write_report", fake_write)
    monkeypatch.setattr(graph_module, "evaluate", lambda **kwargs: [])
    return writer_calls


def _critic_returning(*verdicts):
    """A critic that returns each verdict in turn, then repeats the last."""
    calls = iter(verdicts)
    last = [verdicts[-1]]

    def fake_critique(query, sub_questions, findings, report):
        try:
            last[0] = next(calls)
        except StopIteration:
            pass
        return last[0]

    return fake_critique


def test_approved_draft_is_not_rewritten(fake_pipeline, monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "critique_report",
        _critic_returning(Critique(verdict="approve")),
    )
    result = build_graph().invoke({"query": "q"})

    assert result["revisions"] == 1
    assert len(fake_pipeline) == 1
    assert result["critique"].verdict == "approve"


def test_rejection_sends_the_report_back_with_the_critique(fake_pipeline, monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "critique_report",
        _critic_returning(
            Critique(verdict="revise", issues=["claim in §2 is uncited"], guidance="cite it"),
            Critique(verdict="approve"),
        ),
    )
    result = build_graph().invoke({"query": "q"})

    assert result["revisions"] == 2
    # The first draft is unprompted; the retry must carry the critique, or the
    # loop is just asking for the same draft again.
    assert fake_pipeline[0] is None
    assert fake_pipeline[1].issues == ["claim in §2 is uncited"]


def test_loop_terminates_against_a_never_satisfied_critic(fake_pipeline, monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "critique_report",
        _critic_returning(Critique(verdict="revise", issues=["never happy"])),
    )
    result = build_graph().invoke({"query": "q"})

    # max_revisions=2: without the cap this would recurse until LangGraph's
    # own limit blew up, having burned the free tier on the way.
    assert result["revisions"] == 2
    assert result["report"]  # ships the best draft rather than failing


def test_router_stops_at_the_revision_cap():
    revise = Critique(verdict="revise", issues=["x"])

    assert route_after_critic({"critique": revise, "revisions": 1}) == "writer"
    assert route_after_critic({"critique": revise, "revisions": 2}) == "evaluator"
    assert route_after_critic({"critique": Critique(verdict="approve"), "revisions": 1}) == "evaluator"
