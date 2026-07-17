# research-agents

Multi-agent research & report automation. One query in, a cited report out —
planned, researched, self-critiqued, and written by cooperating agents.

See [plan.md](plan.md) for the roadmap and [summary.md](summary.md) for the pitch.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env   # then fill in your keys
```

You need two free-tier keys:

- `OPENROUTER_API_KEY` — https://openrouter.ai/keys
- `TAVILY_API_KEY` — https://app.tavily.com (1000 searches/month free)

## Run

```bash
.venv/bin/python -m research_agents.cli "how big is the EV battery market in india?"
```

## Layout

```
src/research_agents/
  config.py          settings from .env
  llm.py             LLM client + the generic tool-calling loop agents share
  tools/search.py    Tavily web search: impl + schema the model sees
  agents/            one module per agent
  cli.py             entrypoint
```
