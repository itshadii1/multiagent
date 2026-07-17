"""Orchestration tests with the agents faked out.

The point is the wiring — fan-out, the reducer, the join back to the plan —
so no network and no API keys. Agent output quality is a separate concern,
measured at runtime by `evaluation.py` rather than asserted on here.

The critic loop has its own file (`test_critic_loop.py`); here the critic
always approves, to keep the fan-out under test rather than the reflection.
"""

import time

import pytest

from research_agents import graph as graph_module
from research_agents.graph import build_graph
from research_agents.state import Critique, Finding, Plan, SubQuestion


@pytest.fixture
def fake_agents(monkeypatch):
    def fake_plan(query: str) -> Plan:
        return Plan(
            sub_questions=[
                SubQuestion(id=i, question=f"sub-question {i} about {query}", rationale="r")
                for i in (1, 2, 3)
            ]
        )

    def fake_research(sub_question: SubQuestion) -> Finding:
        time.sleep(0.2)  # stand-in for network latency, so parallelism is observable
        return Finding(
            sub_question_id=sub_question.id,
            question=sub_question.question,
            answer=f"answer to {sub_question.id}",
            sources=[f"https://example.com/{sub_question.id}"],
        )

    monkeypatch.setattr(graph_module, "plan", fake_plan)
    monkeypatch.setattr(graph_module, "research_sub_question", fake_research)

    # The graph runs to completion, so the downstream nodes must be faked too
    # or they reach for the network. Their behavior is tested elsewhere.
    monkeypatch.setattr(
        graph_module,
        "write_report",
        lambda query, findings, sources, critique=None: "# Report\n\nBody [1].",
    )
    monkeypatch.setattr(
        graph_module,
        "critique_report",
        lambda query, sub_questions, findings, report: Critique(verdict="approve"),
    )
    monkeypatch.setattr(graph_module, "evaluate", lambda **kwargs: [])


def test_every_sub_question_gets_a_finding(fake_agents):
    result = build_graph().invoke({"query": "EV batteries in india"})

    assert len(result["sub_questions"]) == 3
    # The reducer must concatenate parallel returns, not let the last writer win.
    assert len(result["findings"]) == 3
    assert {f.sub_question_id for f in result["findings"]} == {1, 2, 3}


def test_findings_carry_sources(fake_agents):
    result = build_graph().invoke({"query": "anything"})

    assert all(f.sources for f in result["findings"])


def test_writer_sees_every_finding(fake_agents, monkeypatch):
    """Fan-in: the writer must not start before all branches land.

    If the researcher→writer edge didn't join, the writer would draft from a
    partial set and the missing research would vanish without an error.
    """
    seen: list[int] = []

    def recording_write(query, findings, sources, critique=None):
        seen.append(len(findings))
        return "# Report"

    monkeypatch.setattr(graph_module, "write_report", recording_write)
    build_graph().invoke({"query": "anything"})

    assert seen == [3], f"writer ran {len(seen)}x, seeing {seen} findings"


def test_researchers_run_in_parallel(fake_agents):
    start = time.perf_counter()
    build_graph().invoke({"query": "anything"})
    elapsed = time.perf_counter() - start

    # Three 0.2s researchers: ~0.2s in parallel, ~0.6s if serial.
    assert elapsed < 0.5, f"researchers look serialized ({elapsed:.2f}s)"
