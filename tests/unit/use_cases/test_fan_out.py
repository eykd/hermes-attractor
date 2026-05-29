"""Unit tests for FAN_OUT/FAN_IN node handlers in advance_on_completion (RED phase M5 US5).

Tests fail because FAN_OUT and FAN_IN branches are not yet implemented in
src/hermes_attractor/use_cases/run_execution.py.

Context.clone() and Context.merge() are already implemented; these tests verify
the FAN_OUT dispatch logic and FAN_IN accumulation.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.card import CardKind, CardResult
from hermes_attractor.domain.constants import MAX_FAN_OUT_WIDTH
from hermes_attractor.domain.exceptions import PipelineValidationError
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
from hermes_attractor.use_cases.run_execution import advance_on_completion

pytestmark = pytest.mark.unit

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
_LATER = datetime.datetime(2026, 1, 1, second=10, tzinfo=datetime.UTC)


def _make_fan_out_pipeline(num_branches: int = 3) -> Pipeline:
    """Build: start -> fan_out -> [branch_0..N] -> fan_in -> exit.

    Args:
        num_branches: Number of parallel branches.

    Returns:
        A Pipeline with FAN_OUT/FAN_IN structure.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    fan_out = Node(node_id="fan_out", shape=NodeShape.FAN_OUT, profile="orchestrator")
    branches = [
        Node(node_id=f"branch_{i}", shape=NodeShape.CODERGEN, profile=f"worker-{i}") for i in range(num_branches)
    ]
    fan_in = Node(node_id="fan_in", shape=NodeShape.FAN_IN, profile="orchestrator")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)

    edges: list[Edge] = [
        Edge(source_id="start", target_id="fan_out"),
    ]
    for branch in branches:
        edges.append(Edge(source_id="fan_out", target_id=branch.node_id))
        edges.append(Edge(source_id=branch.node_id, target_id="fan_in"))
    edges.append(Edge(source_id="fan_in", target_id="exit"))

    return Pipeline(
        spec_id="fan-pipeline",
        nodes=[start, fan_out, *branches, fan_in, exit_],
        edges=edges,
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def _make_run(run_id: str = "run1") -> Run:
    """Build a minimal Run."""
    return Run(
        run_id=run_id,
        spec_id="fan-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={"shared": "value"}),
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_run_node(node_id: str, task_id: str, run_id: str = "run1") -> RunNode:
    """Build a minimal RunNode."""
    return RunNode(
        run_id=run_id,
        node_id=node_id,
        task_id=task_id,
        status=NodeRunStatus.DISPATCHED,
        attempt=1,
        parent_node_ids=[],
    )


# ---------------------------------------------------------------------------
# FAN_OUT: create sibling cards
# ---------------------------------------------------------------------------


def test_advance_on_fan_out_creates_sibling_cards_for_all_branches() -> None:
    """advance_on_completion on FAN_OUT node creates one card per outgoing branch."""
    pipeline = _make_fan_out_pipeline(num_branches=3)
    run = _make_run()
    fan_out_record = _make_run_node("fan_out", "task-fanout")

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = fan_out_record
    run_state.get_run.return_value = run

    task_counter: list[int] = [1]

    def _create_card(card: object) -> str:
        task_id = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        return task_id

    kanban = MagicMock()
    kanban.create_card.side_effect = _create_card
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-fanout",
        event_id=1,
        event_kind="completed",
        summary="Fan-out dispatched.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # 3 branch cards should have been created.
    assert kanban.create_card.call_count == 3, (
        f"Expected 3 branch cards from FAN_OUT, got {kanban.create_card.call_count}"
    )

    # All should be CODERGEN (WORK) cards.
    for call in kanban.create_card.call_args_list:
        card = call[0][0]
        assert card.kind is CardKind.WORK, f"Expected WORK card from FAN_OUT branch, got {card.kind}"


def test_advance_on_fan_out_skips_dangling_edge_target() -> None:
    """FAN_OUT silently skips branch edges whose target node doesn't exist in node_map."""
    pipeline = _make_fan_out_pipeline(num_branches=2)
    run = _make_run()
    fan_out_record = _make_run_node("fan_out", "task-fanout")

    # Add an extra edge from fan_out to a ghost node.
    ghost_edge = Edge(source_id="fan_out", target_id="ghost_node")
    # Build a modified pipeline with the ghost edge.
    bad_pipeline = Pipeline(
        spec_id="fan-pipeline",
        nodes=list(pipeline.nodes),
        edges=[*pipeline.edges, ghost_edge],
        stylesheet=pipeline.stylesheet,
    )

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = fan_out_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    kanban.create_card.return_value = "task-branch"
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-fanout",
        event_id=1,
        event_kind="completed",
        summary="Fan-out.",
        metadata={},
    )

    # Should not raise; ghost_node is silently skipped.
    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=bad_pipeline,
        clock=clock,
    )

    # Only 2 real branches should have gotten cards (ghost_node skipped).
    assert kanban.create_card.call_count == 2


def test_advance_on_fan_out_exceeding_max_width_raises_or_blocks_run() -> None:
    """FAN_OUT with branches exceeding MAX_FAN_OUT_WIDTH blocks the run or raises."""
    # Create a pipeline with MAX_FAN_OUT_WIDTH + 1 branches.
    pipeline = _make_fan_out_pipeline(num_branches=MAX_FAN_OUT_WIDTH + 1)
    run = _make_run()
    fan_out_record = _make_run_node("fan_out", "task-fanout")

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = fan_out_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    kanban.create_card.return_value = "task-branch"
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-fanout",
        event_id=1,
        event_kind="completed",
        summary="Fan-out.",
        metadata={},
    )

    # Should raise PipelineValidationError or transition run to BLOCKED.
    try:
        advance_on_completion(
            card_result=card_result,
            kanban=kanban,
            run_state=run_state,
            pipeline=pipeline,
            clock=clock,
        )
    except PipelineValidationError:
        pass  # Acceptable outcome.
    else:
        # If no exception: the run should have been blocked.
        run_state.save_run.assert_called()
        saved_run: Run = run_state.save_run.call_args[0][0]
        assert saved_run.status is RunStatus.BLOCKED, (
            f"Expected BLOCKED run for FAN_OUT width > {MAX_FAN_OUT_WIDTH}, got {saved_run.status}"
        )


# ---------------------------------------------------------------------------
# FAN_IN: accumulate branch completions
# ---------------------------------------------------------------------------


def test_advance_fan_in_does_not_resolve_until_all_branches_complete() -> None:
    """FAN_IN does not resolve to SUCCEEDED until all its parent branches are done."""
    pipeline = _make_fan_out_pipeline(num_branches=2)
    run = _make_run()
    branch_a_record = _make_run_node("branch_0", "task-a")

    # Only branch_0 done; branch_1 still pending.
    branch_b_record = _make_run_node("branch_1", "task-b")

    nodes: list[RunNode] = [branch_a_record, branch_b_record]

    def _upsert_node(node: RunNode) -> None:
        idx = next(
            (i for i, n in enumerate(nodes) if n.run_id == node.run_id and n.node_id == node.node_id),
            None,
        )
        if idx is not None:
            nodes[idx] = node
        else:
            nodes.append(node)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = branch_a_record
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = nodes
    run_state.upsert_node.side_effect = _upsert_node

    kanban = MagicMock()
    kanban.create_card.return_value = "task-fanin"
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result_a = CardResult(
        task_id="task-a",
        event_id=2,
        event_kind="completed",
        summary="Branch A done.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result_a,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # fan_in should NOT have been dispatched yet (branch_1 still pending).
    fan_in_dispatched = [call[0][0] for call in kanban.create_card.call_args_list if hasattr(call[0][0], "kind")]
    fan_in_node_ids = [
        call[0][0].idempotency_key.value
        for call in kanban.create_card.call_args_list
        if hasattr(call[0][0], "idempotency_key")
    ]
    # None of the created cards should target fan_in.
    assert not any("fan_in" in key for key in fan_in_node_ids), (
        f"fan_in should not be dispatched until all branches complete; got: {fan_in_node_ids}"
    )
    _ = fan_in_dispatched


def test_advance_fan_in_resolves_when_all_branches_complete() -> None:
    """FAN_IN dispatches its card when all parent branches have completed."""
    pipeline = _make_fan_out_pipeline(num_branches=2)
    run = _make_run()

    # Both branches SUCCEEDED.
    branch_a_succeeded = RunNode(
        run_id="run1",
        node_id="branch_0",
        task_id="task-a",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["fan_out"],
    )
    branch_b_dispatched = RunNode(
        run_id="run1",
        node_id="branch_1",
        task_id="task-b",
        status=NodeRunStatus.DISPATCHED,
        attempt=1,
        parent_node_ids=["fan_out"],
    )
    nodes: list[RunNode] = [branch_a_succeeded, branch_b_dispatched]

    def _upsert_node(node: RunNode) -> None:
        idx = next(
            (i for i, n in enumerate(nodes) if n.run_id == node.run_id and n.node_id == node.node_id),
            None,
        )
        if idx is not None:
            nodes[idx] = node
        else:
            nodes.append(node)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = branch_b_dispatched
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = nodes
    run_state.upsert_node.side_effect = _upsert_node

    kanban = MagicMock()
    kanban.create_card.return_value = "task-fanin"
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result_b = CardResult(
        task_id="task-b",
        event_id=3,
        event_kind="completed",
        summary="Branch B done.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result_b,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # fan_in SHOULD have been dispatched now.
    create_calls = [call[0][0] for call in kanban.create_card.call_args_list if hasattr(call[0][0], "idempotency_key")]
    fan_in_calls = [c for c in create_calls if "fan_in" in c.idempotency_key.value]
    call_keys = [c.idempotency_key.value for c in create_calls]
    assert fan_in_calls, f"Expected fan_in card dispatched after all branches complete; got: {call_keys}"
