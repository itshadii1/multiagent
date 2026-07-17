# research-agents

Multi-agent research & report automation. One query in, a cited report out —
planned, researched, self-critiqued, and written by cooperating agents.

See [plan.md](plan.md) for the roadmap and [summary.md](summary.md) for the pitch.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env   # then fill in your keys
```

Two keys, both free tier, neither needs a card:

- `GROQ_API_KEY` — https://console.groq.com/keys
- `TAVILY_API_KEY` — https://app.tavily.com (1000 searches/month)

## Run

The UI (what a recruiter should see) — streams each agent as it works:

```bash
.venv/bin/streamlit run streamlit_app.py
```

Or the CLI:

```bash
.venv/bin/python -m research_agents.cli "how big is the EV battery market in india?"
.venv/bin/python -m research_agents.cli "..." -o report.md    # save the report
```

A run takes a few minutes and burns roughly 10-20 Tavily credits.

## Test

```bash
.venv/bin/python -m pytest tests/ -q
```

Orchestration tests fake the agents out, so they need no keys and cost nothing.

## Architecture

```
planner ──fan-out──▶ researcher ×N ──▶ writer ──▶ critic ──▶ evaluator ──▶ END
                                         ▲           │
                                         └─ revise ◀─┘
```

Two patterns, and they're the reason this is a graph rather than a script:

- **orchestrator-worker** — the planner decides at runtime how many
  researchers exist (`Send`), and they run concurrently.
- **reflection** — the critic can route *backwards* to the writer. A linear
  chain can't express that cycle.

```
src/research_agents/
  config.py          settings from .env
  state.py           typed models agents pass between each other
  llm.py             LLM client, tool-calling loop, JSON completion helper
  graph.py           the LangGraph wiring — the entrypoint for every caller
  evaluation.py      quality checks on the finished report
  tools/search.py    Tavily web search: impl + the schema the model sees
  agents/            one module per agent (planner, researcher, critic, writer)
  cli.py             CLI entrypoint
streamlit_app.py     UI entrypoint (repo root — Streamlit Cloud expects it there)
```

The provider is reached over the OpenAI protocol, so switching LLMs is a
`base_url` + `model` change in `config.py` — no agent code knows the difference.

### Two design decisions worth the interview question

**Citations can't be hallucinated.** The writer emits `[n]` markers, but the
reference list is rendered by *us* from URLs the search tool actually returned.
The model picks which source supports a claim; it cannot invent the source. A
marker outside the registry is caught by `citations_resolve`.

**The graph owns termination, not the critic.** A model asked "is this report
sound?" will always find another improvement, so `max_revisions` lives in the
router. The critic judges; the graph decides when to stop paying.

## Evaluation

Every run scores itself:

| check | kind | what it catches |
|---|---|---|
| `citations_resolve` | rule | a citation pointing at a source no researcher retrieved |
| `citation_coverage` | rule | substantive paragraphs asserting facts with no citation |
| `sub_question_coverage` | LLM judge | a sub-question the report left unanswered |

The rule checks are deterministic, free, and unfoolable. The judge costs a call
and can be wrong, so it's reported alongside them, never instead of them.
