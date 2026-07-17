"""Streamlit UI — the recruiter-facing entrypoint.

Lives at the repo root because Streamlit Community Cloud expects the app file
there. It is a *caller* of `build_graph()`, exactly like the CLI: no agent
logic lives here, and the graph has no idea it's being rendered.

The run takes minutes, so this streams per-node events instead of blocking on
a spinner. That isn't only UX — watching the planner fan out, the critic
reject a draft, and the writer redraft *is* the demo. A progress bar would
hide the one thing worth showing.

Keys come from the environment. Streamlit Cloud injects its secrets manager as
env vars, which pydantic-settings already reads, so nothing here handles keys.
"""

import sys
from pathlib import Path

# Streamlit Cloud installs requirements.txt but never `pip install -e .`, so
# the src/ layout isn't importable there without this. Locally the editable
# install wins and this line is inert.
sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st

from research_agents.graph import build_graph
from research_agents.state import ResearchState, merge_update

st.set_page_config(page_title="Multi-agent research", page_icon="🔍", layout="centered")

st.title("🔍 Multi-agent research")
st.caption(
    "One query in, a cited report out — planned, researched in parallel, "
    "self-critiqued, and written by four cooperating agents."
)

with st.sidebar:
    st.header("How it works")
    st.markdown(
        """
1. **Planner** splits the query into independent sub-questions.
2. **Researchers** run in parallel — one per sub-question, each searching the live web.
3. **Critic** reviews the draft against the findings and can send it back.
4. **Writer** assembles a cited report.

The critic → writer loop is the point: the system self-corrects instead of
answering once.
"""
    )
    st.caption("Groq (llama-3.3-70b) + Tavily search. Runs take a few minutes.")

query = st.text_input(
    "Research query",
    placeholder="e.g. analyze the EV battery market in India",
)
go = st.button("Run research", type="primary", disabled=not query.strip())

if go:
    state: ResearchState = {}
    progress = st.status("Starting…", expanded=True)

    try:
        for event in build_graph().stream({"query": query}, config={"max_concurrency": 3}):
            for node, update in event.items():
                merge_update(state, update)

                if node == "planner":
                    progress.update(label="Planning…")
                    progress.write("**Plan**")
                    for sq in state["sub_questions"]:
                        progress.write(f"{sq.id}. {sq.question}")
                elif node == "researcher":
                    finding = state["findings"][-1]
                    progress.update(
                        label=f"Researching… ({len(state['findings'])}/{len(state['sub_questions'])})"
                    )
                    progress.write(f"✅ {finding.question} — {len(finding.sources)} sources")
                elif node == "writer":
                    progress.update(label=f"Writing (draft {state['revisions']})…")
                    progress.write(f"✍️ Drafted report — revision {state['revisions']}")
                elif node == "critic":
                    critique = state["critique"]
                    if critique.verdict == "approve":
                        progress.write("👍 Critic approved the draft")
                    else:
                        progress.write("🔁 Critic sent it back:")
                        for issue in critique.issues:
                            progress.write(f"  - {issue}")
                elif node == "evaluator":
                    progress.update(label="Done", state="complete")
    except Exception as exc:
        progress.update(label="Run failed", state="error")
        st.error(f"The run failed: {exc}")
        st.stop()

    if not state.get("report"):
        st.error("No report was produced.")
        st.stop()

    st.divider()

    evaluation = state.get("evaluation", [])
    if evaluation:
        st.subheader("Quality checks")
        for result, col in zip(evaluation, st.columns(len(evaluation))):
            col.metric(
                result.name.replace("_", " ").title(),
                f"{result.score:.0%}",
                "pass" if result.passed else "fail",
                delta_color="normal" if result.passed else "inverse",
                help=result.detail,
            )

    st.subheader("Report")
    st.markdown(state["report"])
    st.download_button(
        "Download report (.md)",
        state["report"],
        file_name="report.md",
        mime="text/markdown",
    )

    with st.expander("Raw findings (what the researchers actually retrieved)"):
        for finding in sorted(state["findings"], key=lambda f: f.sub_question_id):
            st.markdown(f"**{finding.sub_question_id}. {finding.question}**")
            st.write(finding.answer)
            for url in finding.sources:
                st.caption(url)
