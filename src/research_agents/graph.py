"""The orchestration graph.

    planner ──Send(fan-out)──▶ researcher ×N ──▶ writer ──▶ critic ──▶ evaluator ──▶ END
                                                   ▲            │
                                                   └── revise ◀─┘

Two patterns worth naming, because they are the reason this is a graph and
not a script:

- **orchestrator-worker.** `Send` makes the fan-out dynamic: the planner
  decides at runtime how many researchers exist, so the graph isn't wired to
  a fixed branch count. LangGraph runs them concurrently and the
  `operator.add` reducer on `findings` merges their returns.
- **reflection.** The critic's conditional edge can route *backwards* to the
  writer. A linear chain cannot express that cycle; it's what a plain
  LangChain chain can't do and why the orchestration layer earns its place.

This module is the entrypoint for every caller — CLI and UI both build the
same graph. Nothing user-facing reaches into the agents directly.
"""

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from research_agents.agents.critic import critique_report
from research_agents.agents.planner import plan
from research_agents.agents.researcher import research_sub_question
from research_agents.agents.writer import build_source_registry, write_report
from research_agents.config import get_settings
from research_agents.evaluation import evaluate
from research_agents.state import ResearchState, SubQuestion


def planner_node(state: ResearchState) -> dict:
    result = plan(state["query"])
    return {"sub_questions": result.sub_questions}


def researcher_node(sub_question: SubQuestion) -> dict:
    # Returns a one-item list; the reducer concatenates across parallel branches.
    return {"findings": [research_sub_question(sub_question)]}


def fan_out_to_researchers(state: ResearchState) -> list[Send]:
    return [Send("researcher", sq) for sq in state["sub_questions"]]


def writer_node(state: ResearchState) -> dict:
    # Built here, once, so the citation numbering the writer is given is the
    # same numbering the evaluator later checks against.
    sources = build_source_registry(state["findings"])
    report = write_report(
        query=state["query"],
        findings=state["findings"],
        sources=sources,
        critique=state.get("critique"),
    )
    return {
        "report": report,
        "sources": sources,
        "revisions": state.get("revisions", 0) + 1,
    }


def critic_node(state: ResearchState) -> dict:
    critique = critique_report(
        query=state["query"],
        sub_questions=state["sub_questions"],
        findings=state["findings"],
        report=state["report"],
    )
    return {"critique": critique}


def route_after_critic(state: ResearchState) -> str:
    """Loop back to the writer, or accept the draft and move on.

    The revision cap is enforced here rather than in the critic: the critic is
    asked whether the report is sound, and a model asked that will keep finding
    work forever. Termination is the graph's call.
    """
    critique = state.get("critique")
    settings = get_settings()

    if critique is None or critique.verdict == "approve":
        return "evaluator"
    if state.get("revisions", 0) >= settings.max_revisions:
        return "evaluator"  # out of retries: ship the draft, evals record the state it's in
    return "writer"


def evaluator_node(state: ResearchState) -> dict:
    return {
        "evaluation": evaluate(
            report=state["report"],
            sources=state.get("sources", []),
            sub_questions=state.get("sub_questions", []),
            findings=state.get("findings", []),
            use_judge=get_settings().use_llm_judge,
        )
    }


def build_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("writer", writer_node)
    graph.add_node("critic", critic_node)
    graph.add_node("evaluator", evaluator_node)

    graph.set_entry_point("planner")
    graph.add_conditional_edges("planner", fan_out_to_researchers, ["researcher"])
    # Plain edge = fan-in: every parallel researcher must finish before the
    # writer runs, which is what makes the writer see all the findings.
    graph.add_edge("researcher", "writer")
    graph.add_edge("writer", "critic")
    graph.add_conditional_edges(
        "critic", route_after_critic, {"writer": "writer", "evaluator": "evaluator"}
    )
    graph.add_edge("evaluator", END)

    return graph.compile()
