# plan.md — multi-agent research & report automation system

## what you're building

a system where multiple AI agents work together to research a topic and produce a structured report. the user gives one query (e.g. "analyze the EV battery market in india"). the system then:

1. **planner agent** — breaks the query into sub-questions.
2. **researcher agents** — each takes a sub-question, searches the web, reads sources, extracts facts.
3. **critic agent** — checks the drafted report for gaps, unsupported claims, and contradictions, then sends it back for a fix if needed.
4. **writer agent** — assembles findings into a final report with citations.

the key differentiator from your tutor project: that one **retrieves and answers** (single agent, RAG). this one **plans, delegates, uses tools, self-critiques, and loops** (multi-agent, agentic). this is what "agentic AI" roles actually screen for.

## why this project fits the job market

- "agentic AI" and "AI agents" are top keywords in 2025-2026 fresher AI listings — this project puts them on your resume with substance behind them.
- AI consultant roles reward "automates a manual knowledge-work task" — report writing is exactly that.
- the critic/self-correction loop shows you understand reliability, not just wiring APIs together. that's the senior signal on a fresher resume.

## resume bullets you'll be able to write (target output)

- built a multi-agent system that automates end-to-end research report generation, using a planner-researcher-critic-writer architecture with a self-correction loop that reduced unsupported claims.
- implemented tool-calling agents (web search + document parsing) orchestrated in langgraph, with per-agent evaluation to measure output quality.

(fill in real numbers once you build and test.)

## tech stack to learn (in order)

### 1. python + async basics (you likely know this — skim)
- `async`/`await`, because agent + tool calls run concurrently.
- pydantic for typed data models (agents pass structured data, not raw strings).

### 2. LLM API + tool calling (core concept)
- how tool/function calling works: the LLM outputs a structured request ("call search with query X"), your code runs it, feeds the result back.
- practice: give one LLM one tool (a calculator or a web-search function) and make it use it.
- learn: anthropic or openai tool-use format; you already touched openrouter, so reuse it.

### 3. langgraph (the orchestration layer — most important)
- this is the big new skill. langgraph models your system as a **graph**: nodes = agents, edges = who runs next.
- learn: `StateGraph`, shared state object, conditional edges (how the critic decides "loop back" vs "done").
- why not plain langchain: langchain chains are linear; langgraph handles loops and branching, which your critic-retry needs.

### 4. web search + retrieval tools
- give researcher agents a real search tool (tavily API is the standard for this — built for agents; free tier exists).
- parse fetched pages into clean text (readability / trafilatura).
- note: you can reuse chromadb here if you want agents to cache/retrieve findings, but it's optional — don't force it.

### 5. multi-agent design patterns
- **orchestrator-worker**: one planner spawns many researchers. learn this pattern specifically.
- **reflection / critic loop**: the self-correction step. this is the pattern that impresses interviewers.
- read: the langgraph docs' multi-agent tutorials cover both.

### 6. evaluation (the part most freshers skip — do it)
- how do you know the report is good? define 2-3 checks: are claims cited? did it answer all sub-questions? is it internally consistent?
- simplest version: use an LLM-as-judge to score outputs, or write rule-based checks.
- being able to say "i measured quality" separates you from people who just built a demo.

## milestones

- **m1:** single agent + one tool (search). it answers one question using live search. (validates tool calling) — **done, verified live**
- **m2:** planner splits a query into sub-questions; researchers answer each in parallel. (validates orchestration) — **done, verified live**
- **m3:** writer assembles a report with citations. (end-to-end happy path) — **done, verified live; citation numbering hardened after real-model failures**
- **m4:** critic agent reviews and triggers a retry loop when the report is weak. (the differentiator) — **done, verified live (critic rejected+approved across runs)**
- **m5:** add evaluation + a simple UI (streamlit or a basic react front end — reuse your react skill). (portfolio polish) — **done; evals run on every live report, app boots**
- **m6:** deploy it, so a recruiter opens a link instead of cloning a repo. — **not started; needs a github push + streamlit cloud connect**

## constraint: zero budget

no paid credits. the stack must stay on free tiers, and that's a design
constraint, not just a shopping choice:

- **groq free tier** (`llama-3.3-70b-versatile`) for the LLM. free, no card,
  real tool calling, very fast. the cost is a **requests-per-minute cap**, which
  parallel researchers will hit — hence backoff + a concurrency cap in the code.
- **tavily free tier** — 1000 searches/month, no card. each researcher run burns
  a few credits, so a full report is roughly 10-20. don't loop it carelessly.
- everything talks the **openai protocol**, so if a free tier dies or you later
  get credits, switching provider is a `base_url` + `model` change in
  `config.py`. no agent code knows which model it's on. keep it that way.

## deployment (m6)

**target: streamlit community cloud.** free, no card, deploys from a github repo,
and has a secrets manager so keys stay out of git. hugging face spaces is the
backup. avoid a react front end + separate backend for now — it needs a job queue
for minutes-long runs and somewhere to host it, which costs money and buys nothing
a recruiter can see.

what this forces on the design (already handled, keep it true):
- **keys from env only, never committed.** streamlit secrets inject as env vars,
  which pydantic-settings already reads. `.env` stays gitignored.
- **the graph is the entrypoint, not the cli.** the ui calls the same
  `build_graph()`; the cli becomes one caller of it, not the interface.
- **a run takes minutes.** the ui must stream progress, not freeze on a spinner.
  langgraph's `.stream()` emits per-node events — build the ui on that, and it
  doubles as a demo of the agents working, which is the thing worth showing.
- **stateless.** no db. a report is generated and rendered; nothing persists.

## progress log

## progress log

### m1 — single agent + search tool (2026-07-17)

scaffolded and importing cleanly. **not yet run against the live APIs** — no keys
present in the environment, so tool calling is unverified end to end.

built:
- `config.py` — pydantic-settings, lazy so imports don't need keys.
- `llm.py` — openrouter client + `run_tool_loop`, the generic tool-calling loop.
  every later agent reuses this; tool errors are fed back to the model as text
  rather than raised, and `max_tool_turns` bounds a runaway loop.
- `tools/search.py` — tavily search. impl + the openai-format schema the model sees,
  kept side by side so they can't drift. `search_depth="basic"` = 1 credit/call.
- `agents/researcher.py` — the m1 agent. system prompt forces search-before-answer
  and a sources list.
- `cli.py`, `pyproject.toml`, `README.md`, `.env.example`.

decisions:
- **openrouter + `anthropic/claude-haiku-4.5` as default** — cheapest thing that
  calls tools reliably. one knob (`MODEL` in `.env`) to trade cost for quality.
- **raw tool calling in m1, langgraph deferred to m2.** m1 exists to make tool
  calling legible; adding a graph to a single node would hide the thing being learned.
- **no chromadb yet.** plan calls it optional — don't force it.

**blocked on:** keys in `.env`, then run the cli once to confirm the loop actually
searches and cites.

### m2 — planner + parallel researchers in langgraph (2026-07-17)

orchestration built and **verified by tests**; the agents themselves are still
unrun against live APIs (no keys yet).

built:
- `state.py` — `SubQuestion`, `Plan`, `Finding`, and `ResearchState`. `findings`
  carries an `operator.add` reducer: parallel researchers each return a one-item
  list and the reducer concatenates them. without it the last writer wins and
  findings silently vanish — the subtle bug worth being able to explain in an interview.
- `agents/planner.py` — query → 3-5 sub-questions via `complete_json`. prompt
  forces *independent* sub-questions, since researchers can't see each other.
  ids are renumbered locally rather than trusted from the model.
- `agents/researcher.py` — now returns a typed `Finding`. **sources are recorded
  from what the search tool actually returned**, not from the model's own
  "Sources:" list, which it can hallucinate. the critic needs ground truth in m4.
- `graph.py` — planner ─`Send`→ researcher ×N → END. `Send` makes the fan-out
  dynamic: the planner decides how many researchers exist at runtime.
- `llm.py` — added `complete_json` (prompt for json, validate with pydantic,
  one repair retry) and `_complete` (backoff/jitter through groq's rate limit).
- `tests/test_graph.py` — 3 passing. agents are monkeypatched, so tests need no
  keys and cost nothing. one asserts researchers actually run *concurrently*
  (3×0.2s finishing under 0.5s), which is the claim the resume bullet makes.

switched off openrouter → **groq** (zero budget; see constraint above).

**blocked on:** same keys. once set: `python -m research_agents.cli "<query>"`
should print a plan and one cited finding per sub-question.

### m3-m5 — writer, critic loop, evals, ui (2026-07-17)

the graph is now complete end to end: planner → researchers ×N → writer →
critic ⇄ writer → evaluator. **still unrun against live APIs** (no keys), but
the full pipeline was driven end to end with the LLM/search layer stubbed and
everything below the agents real — the critic rejected draft 1, the writer
redrafted against the critique, the critic approved, evals scored it. 20 tests
pass. the streamlit app boots and serves.

built:
- `agents/writer.py` — findings → cited report. **the model writes `[n]`
  markers; we render the reference list from `build_source_registry`**, whose
  urls come from what the search tool actually returned. so the model chooses
  which source backs a claim but cannot invent the source — the worst it can do
  is mis-number, which the evals catch. letting the model emit its own url list
  is how citation hallucination gets in. on a retry the critique goes into the
  prompt, so the pass fixes named defects instead of rewording.
- `agents/critic.py` — judges the report *against the findings*, never its own
  knowledge: it hasn't searched, so anything it "knows" is unsourced, and a
  critic arguing from memory injects the unsupported claims it exists to remove.
  prompt explicitly refuses to treat style as a defect, and treats an
  *acknowledged* gap as fine — a gap the researchers left isn't the writer's bug.
- `evaluation.py` — two rule checks (`citations_resolve`, `citation_coverage`),
  deterministic and free, plus one llm judge (`sub_question_coverage`) for the
  semantic question rules can't answer. judge failure degrades to a failed check
  rather than sinking the run: the report is the deliverable, the score is
  commentary. `citation_coverage` counts paragraphs, not claims — a proxy, and
  the docstring says so.
- `graph.py` — writer/critic/evaluator nodes + the conditional back-edge.
- `state.py` — `Critique`, `EvalResult`, and `merge_update`.
- `streamlit_app.py` at repo root, built on `.stream()`.
- `cli.py` — streams progress, `-o` writes the report out.

decisions:
- **the graph owns termination, not the critic.** `max_revisions` lives in
  `route_after_critic`. a model asked "is this sound?" always finds more work;
  an unbounded loop burns the free tier on diminishing edits. at the cap it
  ships the best draft rather than failing — a good-enough report beats none.
- **`merge_update` mirrors the `operator.add` reducer.** streaming in "updates"
  mode yields each node's raw return, so a ui that assigned blindly would let
  each parallel researcher's one-item `findings` list overwrite the last —
  the reducer's bug, reintroduced at the ui boundary. keep the two in step.
- **source registry built once in `writer_node`**, so the numbering the writer
  is given is the numbering the evaluator checks.

**blocked on:** the same keys, now for the whole pipeline. every agent prompt is
still unvalidated against a real model — expect prompt tuning, especially the
critic (likely too harsh at first: watch for it looping to the cap every run).

### first live runs (2026-07-17)

keys in. **the system now runs end to end against live APIs** — three full
reports generated, final one scoring 100%/100%/75% on the evals. every one of
the failures below was invisible to the mocked tests and surfaced only live.
each is now also a regression test (26 passing).

what broke, in order:

1. **llama-3.3-70b can't reliably call tools.** measured 7/8 requests failing
   with groq's `tool_use_failed` — it emits `<function=web_search={...}` instead
   of valid json. the plan's model choice was simply wrong for a tool-calling
   system.
2. **the free tier's real cap is tokens/min, not requests/min.** the plan
   guessed RPM; RPM is a roomy 1000. TPM is the binding constraint, and a
   researcher turn carrying search results (~9k tokens) exceeds some models'
   *entire* budget. measured: scout 30k, llama-3.3-70b 12k, gpt-oss-120b 8k,
   qwen 6k. → **switched to llama-4-scout**, the only free model passing both
   bars (8/8 tool calls AND 30k TPM). also: snippets truncated at 700 chars,
   max_results capped at 5 — a tool result is re-read every later turn, so fat
   snippets are paid for repeatedly.
3. **`tool_use_failed` is retryable.** generation is stochastic; the same
   request usually succeeds on retry. added to `_complete`'s backoff, keyed on
   groq's error code so genuine 400s still raise.
4. **the writer appends its own reference list no matter what the prompt says.**
   twice, in two shapes: empty stubs under `References:`, then — worse —
   entries *with urls* under a prose intro, using its own numbering that
   contradicted the canonical list. prompting against it failed twice, so it's
   now stripped in code (`_strip_model_reference_block`), which is consistent
   with the design: we own the reference list, not the model.
5. **the model renumbers citations if given half a chance.** its in-text [6]
   pointed at a different url than registry #6 — in range, so
   `citations_resolve` passed. fix: the findings block now shows `[n] = url`
   pairs instead of bare numbers, anchoring the mapping. spot-checked live:
   [14] now cites the page that actually makes the claim.
6. **`citation_coverage` was silently skipping most of the report.** models
   write `## heading\ntext` with no blank line, so whole sections started with
   `#` and were excluded (scored 2 paragraphs of a 6-section report). now
   strips heading *lines*, not blocks.

the meta-lesson, worth saying in an interview: mocked tests proved the
orchestration, and every single live failure was in the seam the mocks
replaced — the model's actual behavior. both layers of testing were necessary;
neither was sufficient.

next: m6 — deploy to streamlit community cloud (push to github, connect repo,
paste the two keys into streamlit's secrets manager). also: fill the resume
bullet's "reduced unsupported claims" number with a real before/after from the
evals, and consider making the critic surface the judge's per-question misses.

## what to avoid

- don't over-engineer agent count. 3-4 agents is enough; more looks unfocused.
- don't skip the critic loop — it's the whole reason this beats a plain RAG project.
- don't leave it as a notebook. wrap it so a recruiter can run one command and see a report generate.

## about your tutor project

keep the tutor project **only if** you can clearly explain how it differs from this one in an interview (single-agent retrieval vs multi-agent orchestration). if you can't, they'll look redundant on the resume and you should replace the tutor with something non-AI that shows range — e.g. your flutter minutes-of-meeting app is already strong and different, so two AI projects (this + tutor) is fine as long as they're distinct. this project is distinct enough.
