"""Tests for `merge_update`, the reducer's twin on the streaming side.

Callers that stream in "updates" mode see each node's raw return, not reduced
state. This is the one place that difference has to be handled, and getting it
wrong loses findings silently — the failure mode the reducer exists to prevent,
reintroduced at the UI boundary.
"""

from research_agents.state import Finding, ResearchState, merge_update


def _finding(id: int) -> Finding:
    return Finding(sub_question_id=id, question=f"q{id}", answer="a", sources=[])


def test_parallel_finding_updates_accumulate():
    state: ResearchState = {}

    # Three researcher branches, each emitting its own one-item list.
    merge_update(state, {"findings": [_finding(1)]})
    merge_update(state, {"findings": [_finding(2)]})
    merge_update(state, {"findings": [_finding(3)]})

    assert [f.sub_question_id for f in state["findings"]] == [1, 2, 3]


def test_non_findings_keys_are_overwritten():
    # A redrafted report replaces the old one; it does not append to it.
    state: ResearchState = {"report": "draft 1", "revisions": 1}
    merge_update(state, {"report": "draft 2", "revisions": 2})

    assert state["report"] == "draft 2"
    assert state["revisions"] == 2
