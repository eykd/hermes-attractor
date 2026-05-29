"""Acceptance tests for US4: Human-in-the-loop pause and resume across restart.

Acceptance spec: specs/acceptance-specs/US04-human-in-the-loop.txt

Scenarios covered:

  1. GIVEN a pipeline containing a human-in-the-loop node
     WHEN traversal reaches that node
     THEN the run transitions to PAUSED_HUMAN and the card is blocked.

  2. GIVEN a run paused at a human-in-the-loop node
     WHEN the gateway restarts and the human completes the blocked card
     THEN reconcile resumes the run to SUCCEEDED.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.card import CardKind, CardResult
from hermes_attractor.domain.pipeline import (
    Context,
    Edge,
    Node,
    NodeShape,
    Pipeline,
    StyleRule,
    Stylesheet,
)
from hermes_attractor.domain.run import NodeRunStatus, Run, RunNode, RunStatus
from hermes_attractor.use_cases.reconcile import reconcile
from hermes_attractor.use_cases.run_execution import advance_on_completion, launch_run

pytestmark = pytest.mark.integration

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
_LATER = datetime.datetime(2026, 1, 1, second=30, tzinfo=datetime.UTC)


def _make_human_pipeline() -> Pipeline:
    """Build a pipeline: start -> work -> human_review -> exit.

    ``work`` is a CODERGEN node; ``human_review`` is a HUMAN node.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(
        node_id="work",
        shape=NodeShape.CODERGEN,
        profile="coder",
        prompt="Do the work.",
    )
    human = Node(
        node_id="human_review",
        shape=NodeShape.HUMAN,
        profile="human",
        prompt="Please review the output.",
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="human_review"),
        Edge(source_id="human_review", target_id="exit"),
    ]
    stylesheet = Stylesheet(rules=[StyleRule(selector="*", profile="default")])
    return Pipeline(
        spec_id="human_test",
        nodes=[start, work, human, exit_],
        edges=edges,
        stylesheet=stylesheet,
    )


def _make_fake_state() -> tuple[MagicMock, dict[str, Run], list[RunNode]]:
    """Build a fake RunStateStore backed by in-memory state.

    Returns:
        A tuple of (run_state mock, runs dict, nodes list).
    """
    runs: dict[str, Run] = {}
    nodes: list[RunNode] = []

    def _create_run(run: Run) -> None:
        runs[run.run_id] = run

    def _get_run(run_id: str) -> Run | None:
        return runs.get(run_id)

    def _save_run(run: Run) -> None:
        runs[run.run_id] = run

    def _active_runs() -> list[Run]:
        return [r for r in runs.values() if r.status in (RunStatus.RUNNING, RunStatus.PAUSED_HUMAN)]

    def _upsert_node(node: RunNode) -> None:
        idx = next(
            (i for i, n in enumerate(nodes) if n.run_id == node.run_id and n.node_id == node.node_id),
            None,
        )
        if idx is not None:
            nodes[idx] = node
        else:
            nodes.append(node)

    def _nodes_for_run(run_id: str) -> list[RunNode]:
        return [n for n in nodes if n.run_id == run_id]

    def _get_node_by_task(task_id: str) -> RunNode | None:
        return next((n for n in nodes if n.task_id == task_id), None)

    run_state = MagicMock()
    run_state.create_run.side_effect = _create_run
    run_state.get_run.side_effect = _get_run
    run_state.save_run.side_effect = _save_run
    run_state.active_runs.side_effect = _active_runs
    run_state.upsert_node.side_effect = _upsert_node
    run_state.nodes_for_run.side_effect = _nodes_for_run
    run_state.get_node_by_task.side_effect = _get_node_by_task
    return run_state, runs, nodes


@pytest.mark.xfail(
    reason="PAUSED_HUMAN state transition in advance_on_completion not yet implemented (US4)",
    strict=True,
)
def test_human_node_transitions_run_to_paused_human() -> None:
    """Reaching a HUMAN node transitions the run to PAUSED_HUMAN and blocks the card.

    GIVEN a pipeline with a HUMAN node
    WHEN traversal reaches the HUMAN node
    THEN the run is PAUSED_HUMAN and block_card is called.
    """
    pipeline = _make_human_pipeline()
    run_state, runs, nodes = _make_fake_state()

    task_counter: list[int] = [1]

    def _create_card(card: object) -> str:
        """Create and return a task id."""
        task_id = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        return task_id

    kanban = MagicMock()
    kanban.create_card.side_effect = _create_card

    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph human_test {}"
    clock = MagicMock()
    clock.now.return_value = _NOW

    # Launch the run — this dispatches the first card (for "work" node).
    result = launch_run(
        spec_id="human_test",
        initial_context={},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )
    run_id = result["run_id"]

    # "work" node completes — next is "human_review" (HUMAN node).
    work_node = next(n for n in nodes if n.node_id == "work")
    assert work_node.task_id is not None
    card_result_work = CardResult(
        task_id=work_node.task_id,
        event_id=1,
        event_kind="completed",
        summary="Work done.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result_work,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # The human_review node should have been dispatched with HUMAN card kind.
    human_node_records = [n for n in nodes if n.node_id == "human_review"]
    assert human_node_records, "Expected human_review node to be dispatched"

    # The card created for human_review should be CardKind.HUMAN.
    human_card_calls = [
        call[0][0]
        for call in kanban.create_card.call_args_list
        if hasattr(call[0][0], "kind") and call[0][0].kind is CardKind.HUMAN
    ]
    assert human_card_calls, "Expected a HUMAN card to be created for human_review node"

    # The run should now be PAUSED_HUMAN.
    # (This assertion will FAIL until PAUSED_HUMAN transition is implemented.)
    current_run = runs[str(run_id)]
    assert current_run.status is RunStatus.PAUSED_HUMAN, (
        f"Expected run to be PAUSED_HUMAN after reaching HUMAN node, got {current_run.status}"
    )


def test_run_resumes_after_human_completes_card_via_reconcile() -> None:
    """Run resumes after the human completes the blocked card via reconcile.

    GIVEN a run PAUSED_HUMAN at a human_review node
    WHEN the human completes the blocked card
    THEN reconcile advances the run to SUCCEEDED.
    """
    pipeline = _make_human_pipeline()
    run_state, runs, nodes = _make_fake_state()

    # Seed state: run is PAUSED_HUMAN, human_review node is DISPATCHED.
    run_id = "human-run-1"
    run = Run(
        run_id=run_id,
        spec_id="human_test",
        status=RunStatus.PAUSED_HUMAN,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
        last_seen_event_id=1,  # work's event was processed
    )
    runs[run_id] = run
    human_node_record = RunNode(
        run_id=run_id,
        node_id="human_review",
        task_id="task-human",
        status=NodeRunStatus.DISPATCHED,
        attempt=1,
        parent_node_ids=["work"],
    )
    nodes.append(human_node_record)

    # Human completes the card.
    human_card_result = CardResult(
        task_id="task-human",
        event_id=2,
        event_kind="completed",
        summary="Human review approved.",
        metadata={},
    )

    kanban = MagicMock()
    kanban.create_card.return_value = "task-exit-placeholder"

    event_log = MagicMock()
    event_log.read_since.return_value = [human_card_result]

    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph human_test {}"
    clock = MagicMock()
    clock.now.return_value = _LATER

    # Simulate gateway restart: call reconcile.
    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
    )

    # The run should have advanced from PAUSED_HUMAN to SUCCEEDED.
    final_run = runs[run_id]
    assert final_run.status is RunStatus.SUCCEEDED, (
        f"Expected run to reach SUCCEEDED after human input, got {final_run.status}"
    )
