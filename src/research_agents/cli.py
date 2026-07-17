"""Entrypoint: python -m research_agents.cli "your research query"

One caller of `build_graph()` among several — the Streamlit UI is another.
The graph is the system; this is a thin way to watch it run.
"""

import argparse
import sys

from research_agents.config import get_settings
from research_agents.graph import build_graph
from research_agents.state import ResearchState, merge_update

# What to print as each node finishes, so a multi-minute run isn't a blank screen.
PROGRESS = {
    "planner": lambda s: "\n".join(
        ["Plan:"] + [f"  {sq.id}. {sq.question}" for sq in s["sub_questions"]]
    ),
    # Fires once per parallel branch, so print only the newest finding.
    "researcher": lambda s: (
        f"  researched: {s['findings'][-1].question}"
        f"  ({len(s['findings'][-1].sources)} sources)"
    ),
    "writer": lambda s: f"  drafted report (revision {s['revisions']}, {len(s['sources'])} sources)",
    "critic": lambda s: (
        f"  critic: {s['critique'].verdict}"
        + ("".join(f"\n    - {i}" for i in s["critique"].issues))
    ),
    "evaluator": lambda s: "  evaluated",
}


def _render_evaluation(results) -> str:
    lines = ["## Evaluation", ""]
    for r in results:
        lines.append(f"  [{'PASS' if r.passed else 'FAIL'}] {r.name} ({r.score:.0%}) — {r.detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research-agents")
    parser.add_argument("query", nargs="+", help="the research query")
    parser.add_argument("-o", "--output", help="write the report to this file")
    args = parser.parse_args(argv)

    query = " ".join(args.query)
    settings = get_settings()
    print(f"Query: {query}\n", flush=True)

    final: ResearchState = {}
    # .stream() emits state after each node, which is what makes progress
    # visible on a run that takes minutes.
    for event in build_graph().stream(
        {"query": query},
        # Keeps parallel researchers under Groq's free-tier requests/min cap.
        config={"max_concurrency": settings.max_concurrent_researchers},
    ):
        for node, update in event.items():
            merge_update(final, update)
            render = PROGRESS.get(node)
            if render:
                try:
                    print(render(final), flush=True)
                except Exception:
                    print(f"  {node} done", flush=True)

    if not final.get("report"):
        print("No report produced.", file=sys.stderr)
        return 1

    print("\n" + "=" * 72 + "\n")
    print(final["report"])
    print("\n" + _render_evaluation(final.get("evaluation", [])))

    if args.output:
        with open(args.output, "w") as fh:
            fh.write(final["report"])
        print(f"\nWrote {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
