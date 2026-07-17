# summary.md — multi-agent research & report automation system

## one line
a system of cooperating AI agents that takes a single research query, splits it into sub-questions, searches the web to answer each, self-critiques the draft, and produces a cited report — automating a manual knowledge-work task end to end.

## the four agents
- **planner** — breaks the query into sub-questions.
- **researchers** — run in parallel; each searches the web and extracts facts for one sub-question.
- **critic** — reviews the draft for gaps, unsupported claims, and contradictions; sends it back if weak.
- **writer** — assembles findings into a final cited report.

the critic → retry loop is the core differentiator: the system self-corrects instead of answering once.

## how it differs from your educational tutor project
| | educational tutor | this project |
|---|---|---|
| agents | one | four, cooperating |
| behavior | retrieve → answer | plan → delegate → critique → loop → write |
| pattern | RAG | agentic (orchestrator-worker + reflection) |
| new skill shown | retrieval routing | multi-agent orchestration + self-correction + evals |

## why it's job-relevant (2026)
- hits the exact keywords fresher AI listings use: "agentic AI", "AI agents", "multi-agent".
- frames as business value ("automates research report writing") — what AI consultant screens look for.
- the self-critique loop + evaluation signals reliability thinking, which is rare on fresher resumes.

## core tech stack
- **langgraph** — orchestration (nodes = agents, loops for the critic). the main new skill.
- **LLM tool calling** — via openrouter (you already know it) or anthropic/openai.
- **tavily** — agent-native web search API (free tier).
- **pydantic** — typed data passed between agents.
- **streamlit or react** — simple front end (reuse your react skill).
- **chromadb** — optional, for caching findings (you already know it).

## build order (milestones)
1. one agent + one search tool → answers one question.
2. planner splits query; researchers answer sub-questions in parallel.
3. writer produces a cited report (end-to-end happy path).
4. critic reviews and triggers retry loop. ← the differentiator.
5. add evaluation checks + UI.

## resume bullet (draft — fill in real numbers after building)
- built a multi-agent research automation system (planner-researcher-critic-writer) in langgraph with tool-calling web search and a self-correction loop, plus per-agent evaluation to measure report quality.
