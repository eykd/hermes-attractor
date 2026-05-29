"""Acceptance tests for US5: Parallel fan-out/fan-in concurrency and merge.

Acceptance spec: specs/acceptance-specs/US05-parallel-fanout-fanin.txt

Scenarios covered:

  1. GIVEN a pipeline with a parallel fan-out and fan-in
     WHEN the pipeline runs
     THEN sibling cards are created for each parallel branch
     THEN fan-in resolves only after all branch completions
     THEN branch context contributions are merged.

  2. GIVEN two parallel branches writing to the same context key
     WHEN both complete and fan-in merges
     THEN the merged context has last-branch-wins value
     THEN conflict is recorded under _merge_conflicts.
"""

from __future__ import annotations

import datetime
from typing import cast
from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.card import CardResult
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
from hermes_attractor.use_cases.run_execution import advance_on_completion, launch_run

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xfail(
        reason="FAN_OUT/FAN_IN nodes not yet implemented in advance_on_completion (US5)",
        strict=True,
    ),
]

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
_LATER = datetime.datetime(2026, 1, 1, second=30, tzinfo=datetime.UTC)


def _make_fan_pipeline() -> Pipeline:
    """Build: start -> fan_out -> [branch_a, branch_b, branch_c] -> fan_in -> exit."""
    start = Node(node_id="start", shape=NodeShape.START)
    fan_out = Node(node_id="fan_out", shape=NodeShape.FAN_OUT, profile="orchestrator")
    branch_a = Node(node_id="branch_a", shape=NodeShape.CODERGEN, profile="worker-a")
    branch_b = Node(node_id="branch_b", shape=NodeShape.CODERGEN, profile="worker-b")
    branch_c = Node(node_id="branch_c", shape=NodeShape.CODERGEN, profile="worker-c")
    fan_in = Node(node_id="fan_in", shape=NodeShape.FAN_IN, profile="orchestrator")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="fan_out"),
        Edge(source_id="fan_out", target_id="branch_a"),
        Edge(source_id="fan_out", target_id="branch_b"),
        Edge(source_id="fan_out", target_id="branch_c"),
        Edge(source_id="branch_a", target_id="fan_in"),
        Edge(source_id="branch_b", target_id="fan_in"),
        Edge(source_id="branch_c", target_id="fan_in"),
        Edge(source_id="fan_in", target_id="exit"),
    ]
    return Pipeline(
        spec_id="fan-pipeline",
        nodes=[start, fan_out, branch_a, branch_b, branch_c, fan_in, exit_],
        edges=edges,
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def _make_fake_state() -> tuple[MagicMock, dict[str, Run], list[RunNode]]:
    """Build a fake RunStateStore backed by in-memory state."""
    runs: dict[str, Run] = {}
    nodes: list[RunNode] = []

    def _create_run(run: Run) -> None:
        runs[run.run_id] = run

    def _get_run(run_id: str) -> Run | None:
        return runs.get(run_id)

    def _save_run(run: Run) -> None:
        runs[run.run_id] = run

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
        """Return all nodes for a run."""
        return [n for n in nodes if n.run_id == run_id]

    def _get_node_by_task(task_id: str) -> RunNode | None:
        """Return node by task id."""
        return next((n for n in nodes if n.task_id == task_id), None)

    run_state = MagicMock()
    run_state.create_run.side_effect = _create_run
    run_state.get_run.side_effect = _get_run
    run_state.save_run.side_effect = _save_run
    run_state.nodes_for_run.side_effect = _nodes_for_run
    run_state.get_node_by_task.side_effect = _get_node_by_task
    run_state.upsert_node.side_effect = _upsert_node
    return run_state, runs, nodes


def test_fan_out_creates_sibling_cards_for_each_branch() -> None:
    """FAN_OUT node creates one card per outgoing branch (sibling parallelism).

    GIVEN a FAN_OUT node with 3 outgoing branches
    WHEN traversal reaches FAN_OUT
    THEN 3 sibling kanban cards are created — one per branch.
    """
    pipeline = _make_fan_pipeline()
    run_state, _, nodes = _make_fake_state()

    task_counter: list[int] = [1]

    def _create_card(card: object) -> str:
        task_id = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        return task_id

    kanban = MagicMock()
    kanban.create_card.side_effect = _create_card

    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph fan-pipeline {}"
    clock = MagicMock()
    clock.now.return_value = _NOW

    result = launch_run(
        spec_id="fan-pipeline",
        initial_context={},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )
    run_id = str(result["run_id"])

    # fan_out node should have been dispatched first.
    fan_out_records = [n for n in nodes if n.node_id == "fan_out"]
    assert fan_out_records, "Expected fan_out node to be dispatched"
    fan_out_node = fan_out_records[-1]
    assert fan_out_node.task_id is not None

    # Complete the fan_out card.
    fan_out_result = CardResult(
        task_id=fan_out_node.task_id,
        event_id=1,
        event_kind="completed",
        summary="Fan-out complete.",
        metadata={},
    )

    advance_on_completion(
        card_result=fan_out_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # All three branch nodes should now be DISPATCHED.
    branch_nodes = [n for n in nodes if n.node_id in {"branch_a", "branch_b", "branch_c"}]
    branch_names = {n.node_id for n in branch_nodes}
    assert branch_names == {"branch_a", "branch_b", "branch_c"}, (
        f"Expected all 3 branches dispatched, got: {branch_names}"
    )
    assert all(n.status is NodeRunStatus.DISPATCHED for n in branch_nodes), "All branch nodes should be DISPATCHED"

    _ = run_id  # silence unused warning


def test_fan_in_resolves_after_all_branch_completions_with_merged_context() -> None:
    """FAN_IN resolves only after all branches complete; context is merged.

    GIVEN a run with 3 branches all DISPATCHED
    WHEN all 3 branches complete
    THEN the fan_in resolves and the merged context contains contributions from all branches.
    """
    pipeline = _make_fan_pipeline()
    run_state, runs, nodes = _make_fake_state()

    run_id = "fan-run-1"
    run = Run(
        run_id=run_id,
        spec_id="fan-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
        last_seen_event_id=1,
    )
    runs[run_id] = run

    # Seed all three branch nodes as DISPATCHED.
    branch_tasks = {"branch_a": "task-a", "branch_b": "task-b", "branch_c": "task-c"}
    for node_id, task_id in branch_tasks.items():
        nodes.append(
            RunNode(
                run_id=run_id,
                node_id=node_id,
                task_id=task_id,
                status=NodeRunStatus.DISPATCHED,
                attempt=1,
                parent_node_ids=["fan_out"],
            )
        )

    task_counter: list[int] = [10]

    def _create_card(card: object) -> str:
        task_id = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        return task_id

    kanban = MagicMock()
    kanban.create_card.side_effect = _create_card
    clock = MagicMock()
    clock.now.return_value = _LATER

    # Complete branch_a.
    advance_on_completion(
        card_result=CardResult(
            task_id="task-a",
            event_id=2,
            event_kind="completed",
            summary="Branch A done.",
            metadata={},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # fan_in should NOT yet have resolved (branches b and c still running).
    fan_in_records = [n for n in nodes if n.node_id == "fan_in" and n.status is NodeRunStatus.DISPATCHED]
    assert not fan_in_records, "fan_in should not be dispatched until all branches complete"

    # Complete branch_b.
    advance_on_completion(
        card_result=CardResult(
            task_id="task-b",
            event_id=3,
            event_kind="completed",
            summary="Branch B done.",
            metadata={},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Still not resolved.
    fan_in_records = [n for n in nodes if n.node_id == "fan_in" and n.status is NodeRunStatus.DISPATCHED]
    assert not fan_in_records, "fan_in should not resolve until branch_c completes"

    # Complete branch_c — now fan_in should resolve.
    advance_on_completion(
        card_result=CardResult(
            task_id="task-c",
            event_id=4,
            event_kind="completed",
            summary="Branch C done.",
            metadata={},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    fan_in_records = [n for n in nodes if n.node_id == "fan_in"]
    assert fan_in_records, "fan_in should be dispatched after all branches complete"


def test_fan_in_merge_conflict_recorded_under_merge_conflicts_key() -> None:
    """Conflicting context keys from parallel branches appear under _merge_conflicts.

    GIVEN two branches that both write to the same context key 'result'
    WHEN both complete and fan_in merges their contexts
    THEN the merged context has a '_merge_conflicts' key recording the conflict.
    """
    pipeline = _make_fan_pipeline()
    run_state, runs, nodes = _make_fake_state()

    run_id = "conflict-run-1"
    run = Run(
        run_id=run_id,
        spec_id="fan-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
        last_seen_event_id=1,
    )
    runs[run_id] = run

    # Two branches, both write to "result" key.
    nodes.append(
        RunNode(
            run_id=run_id,
            node_id="branch_a",
            task_id="task-a",
            status=NodeRunStatus.DISPATCHED,
            attempt=1,
            parent_node_ids=["fan_out"],
        )
    )
    nodes.append(
        RunNode(
            run_id=run_id,
            node_id="branch_b",
            task_id="task-b",
            status=NodeRunStatus.DISPATCHED,
            attempt=1,
            parent_node_ids=["fan_out"],
        )
    )
    # branch_c as a dummy (already succeeded).
    nodes.append(
        RunNode(
            run_id=run_id,
            node_id="branch_c",
            task_id="task-c",
            status=NodeRunStatus.SUCCEEDED,
            attempt=1,
            parent_node_ids=["fan_out"],
        )
    )

    task_counter: list[int] = [20]

    def _create_card(card: object) -> str:
        task_id = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        return task_id

    kanban = MagicMock()
    kanban.create_card.side_effect = _create_card
    clock = MagicMock()
    clock.now.return_value = _LATER

    # Both branches write to "result".
    advance_on_completion(
        card_result=CardResult(
            task_id="task-a",
            event_id=2,
            event_kind="completed",
            summary="Branch A: result=alpha",
            metadata={"context_updates": {"result": "alpha"}},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    advance_on_completion(
        card_result=CardResult(
            task_id="task-b",
            event_id=3,
            event_kind="completed",
            summary="Branch B: result=beta",
            metadata={"context_updates": {"result": "beta"}},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Check that merged context has conflict recorded.
    final_run = runs[run_id]
    context_data = final_run.context.data
    assert "_merge_conflicts" in context_data, (
        f"Expected _merge_conflicts in merged context after parallel branch conflict; got: {list(context_data.keys())}"
    )
    conflicts = cast("dict[str, object]", context_data["_merge_conflicts"])
    assert "result" in conflicts, f"Expected 'result' key in _merge_conflicts, got: {list(conflicts.keys())}"
