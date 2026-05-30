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
    GoalGatePolicy,
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


# ---------------------------------------------------------------------------
# FAN_IN retry dedup: retried branch must not block FAN_IN readiness
# ---------------------------------------------------------------------------


def _make_gated_fan_out_pipeline() -> Pipeline:
    """Build: start -> fan_out -> [branch_a (goal-gated, self-retry), branch_b] -> fan_in -> exit.

    branch_a has a GoalGatePolicy that retries itself up to 3 times.

    Returns:
        A Pipeline with a goal-gated FAN_OUT/FAN_IN structure.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    fan_out = Node(node_id="fan_out", shape=NodeShape.FAN_OUT, profile="orchestrator")
    branch_a = Node(
        node_id="branch_a",
        shape=NodeShape.CODERGEN,
        profile="worker-a",
        goal_gate=GoalGatePolicy(retry_target="branch_a", max_attempts=3),
    )
    branch_b = Node(node_id="branch_b", shape=NodeShape.CODERGEN, profile="worker-b")
    fan_in = Node(node_id="fan_in", shape=NodeShape.FAN_IN, profile="orchestrator")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="fan_out"),
        Edge(source_id="fan_out", target_id="branch_a"),
        Edge(source_id="fan_out", target_id="branch_b"),
        Edge(source_id="branch_a", target_id="fan_in"),
        Edge(source_id="branch_b", target_id="fan_in"),
        Edge(source_id="fan_in", target_id="exit"),
    ]
    return Pipeline(
        spec_id="gated-fan-pipeline",
        nodes=[start, fan_out, branch_a, branch_b, fan_in, exit_],
        edges=edges,
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def _make_multi_attempt_state() -> tuple[MagicMock, dict[str, Run], list[RunNode]]:
    """Build a fake RunStateStore that stores RunNodes by (run_id, node_id, attempt).

    Unlike the simple acceptance-test store, this one matches the real SQLite schema:
    the primary key is (run_id, node_id, attempt), so a retried node produces two
    rows — one for attempt=1 (PARTIAL) and one for attempt=2 (SUCCEEDED).
    ``nodes_for_run`` therefore returns both rows, which is exactly the condition
    that triggers the FAN_IN readiness bug (FR-010).

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

    def _upsert_node(node: RunNode) -> None:
        # Key: (run_id, node_id, attempt) — mirrors the real SQLite PRIMARY KEY.
        idx = next(
            (
                i
                for i, n in enumerate(nodes)
                if n.run_id == node.run_id and n.node_id == node.node_id and n.attempt == node.attempt
            ),
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
    run_state.upsert_node.side_effect = _upsert_node
    run_state.nodes_for_run.side_effect = _nodes_for_run
    run_state.get_node_by_task.side_effect = _get_node_by_task
    return run_state, runs, nodes


def test_fan_in_fires_exactly_once_when_one_branch_was_retried() -> None:
    """FAN_IN fires exactly once even when a predecessor branch was retried (attempt=2).

    GIVEN a fan-out pipeline where branch_a is goal-gated and self-retries:
      - fan_out completes -> branch_a (attempt=1) and branch_b (attempt=1) dispatched
      - branch_a attempt=1 completes with gate=FAIL -> branch_a (attempt=2) dispatched
      - branch_a attempt=2 completes with gate=PASS -> two rows exist for branch_a
      - branch_b completes -> all predecessors done
    WHEN branch_b's completion is processed
    THEN the FAN_IN card is dispatched exactly once
    THEN the merged context uses only the latest attempt (attempt=2) per predecessor.

    This is a regression test for FR-010: the readiness length-check must dedup
    predecessor nodes to one row per node_id (latest attempt) before comparing
    against the set of predecessor node_ids.
    """
    pipeline = _make_gated_fan_out_pipeline()
    run_state, runs, nodes = _make_multi_attempt_state()

    run_id = "retry-fan-run-1"
    run = Run(
        run_id=run_id,
        spec_id="gated-fan-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    runs[run_id] = run

    # Seed the fan_out node as already-dispatched (we start just before it completes).
    fan_out_task = "task-fan-out"
    nodes.append(
        RunNode(
            run_id=run_id,
            node_id="fan_out",
            task_id=fan_out_task,
            status=NodeRunStatus.DISPATCHED,
            attempt=1,
            parent_node_ids=["start"],
        )
    )

    task_counter: list[int] = [1]

    def _create_card(card: object) -> str:
        task_id = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        return task_id

    kanban = MagicMock()
    kanban.create_card.side_effect = _create_card
    clock = MagicMock()
    clock.now.return_value = _LATER

    # Step 1: fan_out completes -> branch_a (attempt=1) and branch_b dispatched.
    advance_on_completion(
        card_result=CardResult(
            task_id=fan_out_task,
            event_id=1,
            event_kind="completed",
            summary="fan_out done",
            metadata={},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Verify both branch nodes dispatched.
    branch_a_node = next((n for n in nodes if n.node_id == "branch_a" and n.attempt == 1), None)
    branch_b_node = next((n for n in nodes if n.node_id == "branch_b" and n.attempt == 1), None)
    assert branch_a_node is not None, "branch_a (attempt=1) should be dispatched after fan_out"
    assert branch_b_node is not None, "branch_b (attempt=1) should be dispatched after fan_out"
    assert branch_a_node.task_id is not None, "branch_a (attempt=1) task_id must not be None"
    assert branch_b_node.task_id is not None, "branch_b (attempt=1) task_id must not be None"
    branch_a_task_1: str = branch_a_node.task_id
    branch_b_task: str = branch_b_node.task_id

    # Step 2: branch_a attempt=1 completes with gate=FAIL -> branch_a (attempt=2) dispatched.
    advance_on_completion(
        card_result=CardResult(
            task_id=branch_a_task_1,
            event_id=2,
            event_kind="completed",
            summary="branch_a attempt=1 FAIL",
            metadata={"gate": "fail", "context_updates": {"branch_a_out": "attempt1"}},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Verify branch_a attempt=2 was dispatched (goal gate retry).
    branch_a_attempt2 = next((n for n in nodes if n.node_id == "branch_a" and n.attempt == 2), None)
    assert branch_a_attempt2 is not None, "branch_a attempt=2 should be dispatched after gate fail"
    assert branch_a_attempt2.task_id is not None, "branch_a (attempt=2) task_id must not be None"
    branch_a_task_2: str = branch_a_attempt2.task_id

    # At this point nodes_for_run has: fan_out(1), branch_a(1 PARTIAL), branch_a(2 DISPATCHED), branch_b(1 DISPATCHED)
    branch_a_rows = [n for n in nodes if n.node_id == "branch_a"]
    assert len(branch_a_rows) == 2, f"Expected 2 branch_a rows after retry, got {len(branch_a_rows)}"

    # Step 3: branch_a attempt=2 completes with gate=PASS and a final context update.
    advance_on_completion(
        card_result=CardResult(
            task_id=branch_a_task_2,
            event_id=3,
            event_kind="completed",
            summary="branch_a attempt=2 PASS",
            metadata={"gate": "pass", "context_updates": {"branch_a_out": "attempt2_final"}},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # FAN_IN must NOT have fired yet (branch_b still running).
    fan_in_nodes_before = [n for n in nodes if n.node_id == "fan_in"]
    assert not fan_in_nodes_before, f"fan_in must not fire before branch_b completes; got {fan_in_nodes_before}"

    # Record card-create call count before branch_b completes.
    calls_before_branch_b = kanban.create_card.call_count

    # Step 4: branch_b completes -> FAN_IN should fire exactly once.
    advance_on_completion(
        card_result=CardResult(
            task_id=branch_b_task,
            event_id=4,
            event_kind="completed",
            summary="branch_b done",
            metadata={"context_updates": {"branch_b_out": "b_value"}},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Assert FAN_IN fired exactly once.
    fan_in_nodes_after = [n for n in nodes if n.node_id == "fan_in"]
    assert len(fan_in_nodes_after) == 1, f"Expected exactly 1 fan_in node dispatched; got {len(fan_in_nodes_after)}"

    # Only one new card should have been created (the fan_in card).
    new_cards = kanban.create_card.call_count - calls_before_branch_b
    assert new_cards == 1, f"Expected exactly 1 new card (fan_in) after branch_b completes; got {new_cards}"

    # The merged context should use only the latest attempt (attempt=2) for branch_a.
    final_run = runs[run_id]
    context_data = final_run.context.data
    assert context_data.get("branch_a_out") == "attempt2_final", (
        f"Expected branch_a_out='attempt2_final' (from attempt=2 only); got {context_data.get('branch_a_out')!r}"
    )
    assert context_data.get("branch_b_out") == "b_value", (
        f"Expected branch_b_out='b_value' in merged context; got {context_data.get('branch_b_out')!r}"
    )


def test_fan_in_dedup_uses_highest_attempt_when_nodes_returned_in_descending_order() -> None:
    """FAN_IN dedup selects highest attempt even when nodes_for_run iterates descending.

    When ``nodes_for_run`` returns attempt=2 before attempt=1 for the same node,
    the dedup loop must still retain only the highest attempt (attempt=2) and discard
    the lower attempt (attempt=1). This covers the branch where an existing entry with
    a higher attempt is already present and the loop skips the lower-attempt node.

    GIVEN a fan-out with two branches where branch_a has rows [attempt=2, attempt=1]
      (descending order from the store)
    WHEN branch_b completes and triggers FAN_IN readiness
    THEN FAN_IN fires exactly once
    THEN the merged context contains branch_a's attempt=2 context_updates, not attempt=1.
    """
    pipeline = _make_gated_fan_out_pipeline()

    runs: dict[str, Run] = {}
    # nodes_for_run will return a list built below, in descending attempt order.
    nodes_store: list[RunNode] = []

    def _get_run(run_id: str) -> Run | None:
        return runs.get(run_id)

    def _save_run(run: Run) -> None:
        runs[run.run_id] = run

    def _nodes_for_run(run_id: str) -> list[RunNode]:
        # Return in descending attempt order to exercise the "skip lower attempt" branch.
        return sorted(
            [n for n in nodes_store if n.run_id == run_id],
            key=lambda n: n.attempt,
            reverse=True,
        )

    def _get_node_by_task(task_id: str) -> RunNode | None:
        return next((n for n in nodes_store if n.task_id == task_id), None)

    def _upsert_node(node: RunNode) -> None:
        idx = next(
            (
                i
                for i, n in enumerate(nodes_store)
                if n.run_id == node.run_id and n.node_id == node.node_id and n.attempt == node.attempt
            ),
            None,
        )
        if idx is not None:
            nodes_store[idx] = node
        else:
            nodes_store.append(node)

    run_state = MagicMock()
    run_state.get_run.side_effect = _get_run
    run_state.save_run.side_effect = _save_run
    run_state.nodes_for_run.side_effect = _nodes_for_run
    run_state.get_node_by_task.side_effect = _get_node_by_task
    run_state.upsert_node.side_effect = _upsert_node

    run_id = "retry-fan-run-desc"
    run = Run(
        run_id=run_id,
        spec_id="gated-fan-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    runs[run_id] = run

    # Pre-populate: branch_a with attempt=2 (SUCCEEDED, latest) and attempt=1 (PARTIAL, stale).
    nodes_store.append(
        RunNode(
            run_id=run_id,
            node_id="branch_a",
            task_id="task-a-2",
            status=NodeRunStatus.SUCCEEDED,
            attempt=2,
            parent_node_ids=["fan_out"],
            context_updates={"branch_a_out": "attempt2_value"},
        )
    )
    nodes_store.append(
        RunNode(
            run_id=run_id,
            node_id="branch_a",
            task_id="task-a-1",
            status=NodeRunStatus.PARTIAL,
            attempt=1,
            parent_node_ids=["fan_out"],
            context_updates={"branch_a_out": "attempt1_stale"},
        )
    )
    # branch_b dispatched (attempt=1).
    nodes_store.append(
        RunNode(
            run_id=run_id,
            node_id="branch_b",
            task_id="task-b-1",
            status=NodeRunStatus.DISPATCHED,
            attempt=1,
            parent_node_ids=["fan_out"],
        )
    )

    task_counter: list[int] = [50]

    def _create_card(card: object) -> str:
        task_id = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        return task_id

    kanban = MagicMock()
    kanban.create_card.side_effect = _create_card
    clock = MagicMock()
    clock.now.return_value = _LATER

    # branch_b completes: nodes_for_run returns [branch_a attempt=2, branch_a attempt=1, branch_b attempt=1]
    # The dedup loop must keep attempt=2 for branch_a and skip attempt=1.
    advance_on_completion(
        card_result=CardResult(
            task_id="task-b-1",
            event_id=5,
            event_kind="completed",
            summary="branch_b done",
            metadata={"context_updates": {"branch_b_out": "b_final"}},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # FAN_IN should have fired exactly once.
    fan_in_nodes = [n for n in nodes_store if n.node_id == "fan_in"]
    assert len(fan_in_nodes) == 1, f"Expected exactly 1 fan_in node; got {len(fan_in_nodes)}"

    # Merged context must use attempt=2 for branch_a (not attempt=1).
    final_run = runs[run_id]
    context_data = final_run.context.data
    assert context_data.get("branch_a_out") == "attempt2_value", (
        f"Expected attempt=2 context_updates; got {context_data.get('branch_a_out')!r}"
    )
    assert context_data.get("branch_b_out") == "b_final", (
        f"Expected branch_b_out='b_final'; got {context_data.get('branch_b_out')!r}"
    )
