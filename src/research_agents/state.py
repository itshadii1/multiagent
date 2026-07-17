"""Typed state passed between agents.

Agents exchange these models, never raw strings — so a malformed hand-off
fails at the boundary instead of silently corrupting the report.
"""

import operator
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field


class SubQuestion(BaseModel):
    id: int = Field(description="Stable id, 1-based, used to join findings back to the plan.")
    question: str
    rationale: str = Field(description="Why answering this advances the main query.")


class Plan(BaseModel):
    sub_questions: list[SubQuestion]


class Finding(BaseModel):
    sub_question_id: int
    question: str
    answer: str
    sources: list[str] = Field(
        default_factory=list,
        description="URLs the search tool actually returned during this agent's run.",
    )


class Critique(BaseModel):
    verdict: Literal["approve", "revise"]
    issues: list[str] = Field(
        default_factory=list,
        description="Specific defects: unsupported claims, gaps, contradictions.",
    )
    guidance: str = Field(
        default="",
        description="What the writer should change on the next pass.",
    )


class EvalResult(BaseModel):
    """One quality check. `score` is 0-1 so checks can be averaged."""

    name: str
    passed: bool
    score: float
    detail: str


class ResearchState(TypedDict, total=False):
    """Shared graph state.

    `findings` uses an `operator.add` reducer because researcher nodes run in
    parallel and each returns its own one-item list; the reducer concatenates
    them instead of letting the last writer win.

    The rest are written by one node at a time, so they need no reducer:
    last-write-wins is exactly right for a report being revised.
    """

    query: str
    sub_questions: list[SubQuestion]
    findings: Annotated[list[Finding], operator.add]
    sources: list[str]
    report: str
    critique: Critique | None
    # Bounds the critic loop: the critic can always find something to improve,
    # so the graph, not the model, decides when to stop.
    revisions: int
    evaluation: list[EvalResult]


def merge_update(accumulated: ResearchState, update: dict) -> None:
    """Fold one `.stream()` update into a running state, in place.

    Streaming in "updates" mode yields each node's raw return rather than the
    reduced state, so a caller that assigns blindly would let each parallel
    researcher's one-item `findings` list overwrite the last. This mirrors the
    `operator.add` reducer for exactly that key — keep the two in step.
    """
    for key, value in update.items():
        if key == "findings":
            accumulated.setdefault("findings", []).extend(value)
        else:
            accumulated[key] = value
