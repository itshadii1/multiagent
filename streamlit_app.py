"""Streamlit UI — the recruiter-facing entrypoint.

Lives at the repo root because Streamlit Community Cloud expects the app file
there. It is a *caller* of `build_graph()`, exactly like the CLI: no agent
logic lives here, and the graph has no idea it's being rendered. All styling
lives in `ui.py`, so this file stays about *what* to show, not *how* it looks.

The run takes minutes, so this streams per-node events instead of blocking on a
spinner. That isn't only UX — watching the planner fan out, the critic reject a
draft, and the writer redraft *is* the demo. A progress bar would hide the one
thing worth showing.

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

import ui
from research_agents.graph import build_graph
from research_agents.state import ResearchState, merge_update

st.set_page_config(page_title="Multi-agent research", page_icon="🧠", layout="centered")

# --- theme -------------------------------------------------------------------
# Streamlit's native theme is fixed at load, so the user toggle drives injected
# CSS instead. Read the choice first (it renders into the sidebar regardless of
# script position), then paint the whole page before building the body.
with st.sidebar:
    st.markdown("<p class='section-label'>Appearance</p>", unsafe_allow_html=True)
    theme_choice = st.segmented_control(
        "Appearance",
        options=["Dark", "Light"],
        default="Dark",
        key="theme_choice",
        label_visibility="collapsed",
    )

theme = "light" if theme_choice == "Light" else "dark"
st.markdown(ui.theme_css(theme), unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<p class='section-label'>How it works</p>", unsafe_allow_html=True)
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
    st.caption("Groq (llama-4-scout) + Tavily search. Runs take a few minutes.")

# --- hero --------------------------------------------------------------------
st.markdown(
    ui.hero_html(
        "Multi-agent research",
        "One query in, a cited report out — planned, researched in parallel, "
        "self-critiqued, and written by four cooperating agents.",
    ),
    unsafe_allow_html=True,
)
st.markdown(ui.pipeline_html(), unsafe_allow_html=True)

# --- query input + example chips --------------------------------------------
# The query lives in session_state so an example chip can fill the box: the chip
# sets the value and reruns *before* the text_input is instantiated below, which
# is the only order Streamlit allows a keyed widget's state to be set from code.
st.session_state.setdefault("query", "")

st.markdown("<p class='section-label'>Try an example</p>", unsafe_allow_html=True)
chip_cols = st.columns(len(ui.EXAMPLE_QUERIES))
for example, col in zip(ui.EXAMPLE_QUERIES, chip_cols):
    if col.button(example, key=f"ex-{example}", type="secondary"):
        st.session_state["query"] = example
        st.rerun()

query = st.text_input(
    "Research query",
    key="query",
    placeholder="e.g. analyze the EV battery market in India",
)
go = st.button("Run research", type="primary", disabled=not query.strip())

# --- run ---------------------------------------------------------------------
if go and query.strip():
    state: ResearchState = {}
    progress = st.status("Starting…", expanded=True)

    try:
        for event in build_graph().stream(
            {"query": query.strip()}, config={"max_concurrency": 3}
        ):
            for node, update in event.items():
                merge_update(state, update)

                if node == "planner":
                    progress.update(label="Planning…")
                    progress.write("**Plan**")
                    for sq in state.get("sub_questions", []):
                        progress.write(f"{sq.id}. {sq.question}")
                elif node == "researcher":
                    # Report exactly the findings this event delivered rather
                    # than indexing the accumulated list, so a batched update
                    # can't slip past the end or double-count.
                    total = len(state.get("sub_questions", []))
                    for finding in update.get("findings", []):
                        progress.write(
                            f"✅ {finding.question} — {len(finding.sources)} sources"
                        )
                    progress.update(
                        label=f"Researching… ({len(state.get('findings', []))}/{total})"
                    )
                elif node == "writer":
                    progress.update(label=f"Writing (draft {state.get('revisions', 1)})…")
                    progress.write(f"✍️ Drafted report — revision {state.get('revisions', 1)}")
                elif node == "critic":
                    critique = state.get("critique")
                    if critique and critique.verdict == "approve":
                        progress.write("👍 Critic approved the draft")
                    elif critique:
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

    # Each results section is gated on its own data: a run that fails mid-writer
    # can leave findings without a report, or a report without evals. Render
    # what exists; don't assume they arrive together.
    evaluation = state.get("evaluation", [])
    if evaluation:
        st.markdown("<p class='section-label'>Quality checks</p>", unsafe_allow_html=True)
        for result, col in zip(evaluation, st.columns(len(evaluation))):
            col.metric(
                result.name.replace("_", " ").title(),
                f"{result.score:.0%}",
                "pass" if result.passed else "fail",
                delta_color="normal" if result.passed else "inverse",
                help=result.detail,
            )

    st.markdown("<p class='section-label'>Report</p>", unsafe_allow_html=True)
    st.markdown("<div class='report-frame'>", unsafe_allow_html=True)
    st.markdown(state["report"])
    st.markdown("</div>", unsafe_allow_html=True)
    st.download_button(
        "Download report (.md)",
        state["report"],
        file_name="report.md",
        mime="text/markdown",
    )

    findings = state.get("findings", [])
    if findings:
        with st.expander("Raw findings (what the researchers actually retrieved)"):
            for finding in sorted(findings, key=lambda f: f.sub_question_id):
                st.markdown(f"**{finding.sub_question_id}. {finding.question}**")
                st.write(finding.answer)
                for url in finding.sources:
                    st.caption(url)
