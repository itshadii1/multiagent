# summary.md — multi-agent research & report automation system

## one line
a system of cooperating AI agents that takes a single research query, splits it
into sub-questions, searches the web to answer each, self-critiques the draft,
and produces a cited report — automating a manual knowledge-work task end to end.

---

## the dead-simple version (read this first)

**what it does:** you type one question. you get back a written report with real
sources, like a mini research analyst did it for you.

**the everyday example:** imagine you ask an intern, "write me a two-page brief
on the EV battery market in India." a good intern doesn't just start typing. they
break the question into parts, google each part, write a draft, re-read it to
catch weak spots, and hand you a clean version with links. this app is four AI
"interns" doing exactly that, automatically, in about two minutes.

**why it's useful:** researching and writing a sourced report is slow, boring
knowledge work that people do by hand every day — consultants, analysts,
students. this automates the whole loop, not just one step.

**why it's different from a chatbot:** ask ChatGPT the same question and it
answers *once*, instantly, and sometimes makes up its sources. this system
double-checks itself — one agent's only job is to catch weak or unsupported
claims and send the draft back to be fixed. that "check your own work" loop is
the whole point.

**the one-sentence resume/interview answer:** "it's a team of AI agents that
plan, search the web, write, and critique each other to produce a cited research
report from a single question — so it automates research writing end to end."

---

## why i built it (the intuition)

start with the thing a person actually does. someone asks you "how big is the EV
battery market in india?" you don't answer in one shot. you:

1. break it into smaller questions you can actually look up,
2. go search each one,
3. write it up,
4. **re-read your own draft and notice what's weak**, then fix it.

step 4 is the interesting one. it's the difference between a first draft and
something you'd send. and it's the step almost every AI demo skips — ask a
chatbot a research question and it answers *once*, confidently, sometimes with
sources it made up.

so the intuition was: **don't build one AI that answers. build a small team that
works the way a careful person works.** one agent plans, several go research in
parallel, one writes, and one plays the reviewer who sends the draft back.

the second intuition was about trust. the failure everyone knows is an AI citing
a source that doesn't exist. i didn't want to *ask* the model to stop doing that
— asking is not a fix. i wanted a design where it *can't*.

and why this project specifically: my tutor project retrieves and answers — one
agent, RAG. that's a solved shape. this one plans, delegates, uses tools,
critiques itself, and loops. that's the shape "agentic AI" roles actually screen
for, and it's a genuinely harder problem, not the same problem with more parts.

---

## how i solved it

### the team of four
| agent | job |
|---|---|
| **planner** | turns the one big query into 3-5 smaller, searchable questions |
| **researchers** | one per question, all running at the same time; each searches the live web |
| **writer** | turns everything gathered into a cited report |
| **critic** | reviews the draft against the research, and can send it back |

### the three problems that were actually hard

**1. "how do i stop it inventing sources?"**

split the job. the writer only writes markers like `[2]`. the actual list of
links is printed by *my code*, from URLs the search tool really returned.

so the model chooses *which* source backs a claim, but never gets to write a URL.
it literally cannot invent one — the worst it can do is point at the wrong
number, and a check catches that automatically. the fix is structural, not a
polite instruction in a prompt.

**2. "when does the loop stop?"**

the critic reviews the draft and can reject it. but if you ask a model "is this
good enough?" it will *always* find something to improve — that's a loop that
never ends and burns through the free tier.

so the critic doesn't get to decide when to stop. it only gives a verdict. my
code counts the revisions and calls it after 2. **the model judges; the program
decides.** and at the limit it ships the best draft rather than failing — a
good-enough report beats no report.

**3. "how do i know it's any good?"**

"looks good to me" isn't a measurement. so every run scores itself:

- **do all the citations point at real retrieved sources?** (a rule — free,
  deterministic, impossible to fool)
- **does every paragraph making a claim actually cite something?** (a rule)
- **did the report answer every sub-question?** (this one needs an AI to judge,
  because "was this answered" is a judgement call, not a pattern)

the rule-based ones are the honest ones. the AI judge can be wrong, so it's
reported *next to* them, never instead of them.

### keeping it free
zero budget was a design constraint, not just a shopping choice. groq's free tier
for the LLM, tavily's free tier for search. groq caps requests per minute, and
parallel researchers will hit that — so the code has backoff and a concurrency
cap. everything talks the OpenAI protocol, so swapping providers later is a
two-line config change; no agent code knows which model it's on.

---

## the workflow (what happens when you type a query)

```
        "analyze the EV battery market in india"
                        │
                        ▼
                   ┌─────────┐
                   │ PLANNER │  splits it into 3-5 searchable questions
                   └─────────┘
                        │
          ┌─────────────┼─────────────┐    ← all at the same time
          ▼             ▼             ▼
     ┌────────┐    ┌────────┐    ┌────────┐
     │RESEARCH│    │RESEARCH│    │RESEARCH│  each searches the live web
     └────────┘    └────────┘    └────────┘
          └─────────────┼─────────────┘
                        ▼                    ← waits for ALL of them
                   ┌─────────┐
             ┌────▶│ WRITER  │  drafts the report with [1] [2] markers
             │     └─────────┘
             │           │
             │           ▼
             │     ┌─────────┐
             │     │ CRITIC  │  checks the draft against the research
             │     └─────────┘
             │           │
             └───────────┤  "revise" → back to the writer, with the reasons
              (max 2x)   │
                         │  "approve" ↓
                   ┌───────────┐
                   │ EVALUATOR │  scores it: citations valid? all questions answered?
                   └───────────┘
                         │
                         ▼
                 cited report + scores
```

step by step:

1. **you type one query.**
2. **the planner** breaks it into 3-5 questions. they must be *independent* —
   researchers work in parallel and can't see each other, so a question that
   needs another's answer first would research badly.
3. **the researchers** fan out, one per question, all at once. each searches the
   web and pulls out facts. every URL it actually opened gets recorded — that
   list becomes the ground truth for citations later.
4. **everything waits** until the last researcher finishes, so the writer sees
   the complete picture and no research goes missing.
5. **the writer** drafts the report, citing with `[n]` markers.
6. **the critic** reads the draft *against the raw findings* — not against its
   own knowledge, since it never searched and anything it "knows" is unsourced.
   it looks for uncited claims, unanswered questions, and contradictions.
7. **if it rejects**, the draft goes back to the writer *with the specific
   reasons attached*, so the rewrite fixes named problems instead of just
   rewording. up to twice.
8. **the evaluator** scores the final report.
9. **you get** a cited report plus its quality scores.

the loop at step 7 is the whole point — the system corrects itself instead of
answering once and hoping.

---

## how it differs from my educational tutor project
| | educational tutor | this project |
|---|---|---|
| agents | one | four, cooperating |
| behavior | retrieve → answer | plan → delegate → critique → loop → write |
| pattern | RAG | agentic (orchestrator-worker + reflection) |
| new skill shown | retrieval routing | multi-agent orchestration + self-correction + evals |

## why it's job-relevant (2026)
- hits the exact keywords fresher AI listings use: "agentic AI", "AI agents",
  "multi-agent".
- frames as business value ("automates research report writing") — what AI
  consultant screens look for.
- the self-critique loop + evaluation signals reliability thinking, which is rare
  on fresher resumes.

## core tech stack
- **langgraph** — orchestration (nodes = agents, and the loop back to the writer).
- **groq** (llama-3.3-70b) — the LLM, free tier, real tool calling.
- **tavily** — agent-native web search, free tier.
- **pydantic** — typed data passed between agents, so a bad hand-off fails loudly.
- **streamlit** — the UI, streaming each agent as it works.

## status
- **runs live, end to end.** three real reports generated against groq + tavily;
  the latest scored 100% on citation validity, 100% on citation coverage, and
  75% on sub-question coverage — and the evals said so honestly.
- 26 tests pass. every bug the live runs exposed became a regression test.
- the live runs forced real engineering: the original model choice couldn't
  actually call tools (measured, then switched), the free tier's binding limit
  turned out to be tokens/min not requests/min (measured, then fixed), and the
  model kept trying to write its own reference list (now stripped in code).
- next: deploy to streamlit cloud so it's a link, not a repo.

## resume bullet (draft — fill in real numbers after running it live)
- built a multi-agent research automation system (planner-researcher-critic-writer)
  in langgraph with tool-calling web search and a self-correction loop, plus
  per-agent evaluation to measure report quality.

---

## m7 — UI redesign + light/dark theme (2026-07-18)

the pipeline was already done and honest, but it shipped behind the default
streamlit skin — and a recruiter judges a link in the first three seconds. this
pass is **presentation only**: not a single agent, graph, or eval line changed,
and all 26 tests still pass. what changed is how the same run looks and how solid
the UI is when a run goes sideways.

**made the existing UI concrete before adding to it.** three thin spots in
`streamlit_app.py` only bit on a real run, so they were closed first:
- the run now gates on a stripped query in one place, so whitespace-only input
  can't start a pointless (paid) run.
- the researcher progress line used to read `findings[-1]` off the accumulated
  list, assuming each streamed update carried exactly one finding. it now reports
  the findings *that event actually delivered*, so a batched update can't index
  past the end or double-count.
- the results block assumed report, evals, and findings all arrive together. a
  run that dies mid-writer breaks that assumption, so each section now renders
  behind its own presence check instead of one shared one.

**the design work (what a visitor now sees):**
- **dropped the magnifying-glass emoji** from the title; the wordmark carries it.
- **light + dark mode, toggled live in the sidebar.** streamlit fixes its native
  theme at page load, so a runtime switch can't go through that path — the toggle
  instead picks a token set and injects it as CSS variables, restyling the app
  shell *and* the sidebar (whose fill streamlit paints with high specificity, so
  it needed a targeted override). default is dark, matching the original look.
- **a gradient hero wordmark** and one-line pitch.
- **a static agent-pipeline strip** (planner → researchers → writer ⇄ critic →
  evaluator, with the critic's revise-loop marked) shown *before* a run — so the
  four-agent architecture reads even on an idle page, which is the whole thing
  worth showing.
- **clickable example queries** that fill the input in one click, lowering the
  "what do I even type" barrier for a visitor who won't invent a query.
- **restyled results** — quality checks as framed metric cards, the report in a
  bordered surface; the `.md` download and raw-findings expander are kept.

**where it lives:** all styling is isolated in `ui.py` at the repo root (theme
tokens, the CSS builder, small HTML render helpers, the example list), so
`streamlit_app.py` stays a thin caller of `build_graph()` — same discipline as
the CLI. a `.streamlit/config.toml` sets a dark base theme so the very first
paint, before any CSS injects, already looks intentional (no light-mode flash).

verified live in a browser: both themes repaint fully (sidebar included), the
theme toggle round-trips, and the example chips populate the query box and enable
the run button.

**improvement ideas parked for next time (deliberately not built here, to keep
this pass presentation-only):**
- **PDF export** of the report alongside the existing `.md` download — recruiters
  skim, they don't clone.
- **per-agent timing** surfaced in the progress stream — turns the run into a
  visible benchmark and backs a latency number on the resume.
- **a model picker in the UI** — the config already makes the LLM a one-knob
  swap, so surfacing it would demo the provider-agnostic design live.
- **the "reduced unsupported claims" number** — run the evals with the critic
  loop on vs off and record the delta; still the strongest resume line, still
  unfilled.
