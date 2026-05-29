"""Acceptance tests for US3: Crash recovery — restart mid-run, no re-execution.

Acceptance spec: specs/acceptance-specs/US03-crash-recovery.txt

Scenarios covered:

  1. GIVEN a running pipeline that has completed some nodes
     WHEN the Hermes gateway is killed and restarted mid-run
     THEN the run resumes from the correct position
     THEN already-completed nodes are not re-executed (idempotency key dedup)
     THEN the run reaches the same final outcome.
"""

from __future__ import annotations

import datetime
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
from hermes_attractor.domain.run import IdempotencyKey, NodeRunStatus, Run, RunNode, RunStatus
from hermes_attractor.use_cases.reconcile import reconcile
from hermes_attractor.use_cases.run_execution import advance_on_completion

pytestmark = pytest.mark.integration

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
_LATER = datetime.datetime(2026, 1, 1, second=30, tzinfo=datetime.UTC)


def _make_two_node_pipeline() -> Pipeline:
    """Build a minimal linear pipeline: start -> node_a -> node_b -> exit.

    Both ``node_a`` and ``node_b`` are CODERGEN nodes with the same profile.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    node_a = Node(node_id="node_a", shape=NodeShape.CODERGEN, prompt="Do step A.", profile="worker")
    node_b = Node(node_id="node_b", shape=NodeShape.CODERGEN, prompt="Do step B.", profile="worker")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="node_a"),
        Edge(source_id="node_a", target_id="node_b"),
        Edge(source_id="node_b", target_id="exit"),
    ]
    stylesheet = Stylesheet(rules=[StyleRule(selector="*", profile="worker")])
    return Pipeline(
        spec_id="crash_test",
        nodes=[start, node_a, node_b, exit_],
        edges=edges,
        stylesheet=stylesheet,
    )


def _make_fake_kanban() -> tuple[MagicMock, list[str], list[str]]:
    """Build a fake KanbanBoard that deduplicates by idempotency key.

    Returns:
        A tuple of (kanban mock, created_task_ids list, created_idempotency_keys list).
    """
    created_task_ids: list[str] = []
    created_idempotency_keys: list[str] = []
    task_counter: list[int] = [1]

    def _create_card(card: object) -> str:
        """Record idempotency key and return a task id (or existing id on dedup)."""
        key = str(card.idempotency_key.value)  # type: ignore[union-attr]
        if key in created_idempotency_keys:
            idx = created_idempotency_keys.index(key)
            return created_task_ids[idx]
        created_idempotency_keys.append(key)
        task_id = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        created_task_ids.append(task_id)
        return task_id

    kanban = MagicMock()
    kanban.create_card.side_effect = _create_card
    return kanban, created_task_ids, created_idempotency_keys


def _make_fake_run_state(
    run: Run,
    initial_nodes: list[RunNode],
) -> MagicMock:
    """Build a fake RunStateStore backed by in-memory dicts.

    Args:
        run: The initial Run to seed the store with.
        initial_nodes: Initial RunNode records.

    Returns:
        A MagicMock with in-memory state behaviour.
    """
    runs: dict[str, Run] = {run.run_id: run}
    nodes: list[RunNode] = list(initial_nodes)

    def _active_runs() -> list[Run]:
        """Return all RUNNING or PAUSED_HUMAN runs."""
        return [r for r in runs.values() if r.status in (RunStatus.RUNNING, RunStatus.PAUSED_HUMAN)]

    def _get_run(run_id: str) -> Run | None:
        """Return run from store."""
        return runs.get(run_id)

    def _save_run(updated_run: Run) -> None:
        """Update run in store."""
        runs[updated_run.run_id] = updated_run

    def _upsert_node(node: RunNode) -> None:
        """Upsert node in store."""
        existing_idx = next(
            (i for i, n in enumerate(nodes) if n.run_id == node.run_id and n.node_id == node.node_id),
            None,
        )
        if existing_idx is not None:
            nodes[existing_idx] = node
        else:
            nodes.append(node)

    def _nodes_for_run(run_id: str) -> list[RunNode]:
        """Return all nodes for a run."""
        return [n for n in nodes if n.run_id == run_id]

    def _get_node_by_task(task_id: str) -> RunNode | None:
        """Return node by task id."""
        return next((n for n in nodes if n.task_id == task_id), None)

    run_state = MagicMock()
    run_state.active_runs.side_effect = _active_runs
    run_state.get_run.side_effect = _get_run
    run_state.save_run.side_effect = _save_run
    run_state.upsert_node.side_effect = _upsert_node
    run_state.nodes_for_run.side_effect = _nodes_for_run
    run_state.get_node_by_task.side_effect = _get_node_by_task
    # Expose runs dict for assertions.
    run_state._runs = runs  # noqa: SLF001
    return run_state


def test_reconcile_resumes_run_without_re_executing_completed_nodes() -> None:
    """Reconcile resumes a run without re-executing already-completed nodes.

    Scenario:
    1. node_a was dispatched (event_id cursor=0).
    2. node_a completed (event_id=1) but crash prevented cursor advance.
    3. Reconcile replays event_id=1: marks node_a SUCCEEDED, dispatches node_b.
    4. node_a is NOT re-dispatched (idempotency key dedup).
    5. Cursor advanced to event_id=1.
    """
    run_id = "crash-test-run"
    node_a_key = IdempotencyKey.for_node(run_id, "node_a", 1)
    run = Run(
        run_id=run_id,
        spec_id="crash_test",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
        last_seen_event_id=0,
    )
    node_a_record = RunNode(
        run_id=run_id,
        node_id="node_a",
        task_id="task-001",
        status=NodeRunStatus.DISPATCHED,
        attempt=1,
        parent_node_ids=["start"],
    )

    pipeline = _make_two_node_pipeline()
    kanban, _, created_idempotency_keys = _make_fake_kanban()
    # Pre-seed task-001 as an already-created idempotency key so dedup works.
    created_idempotency_keys.append(node_a_key.value)
    kanban.create_card.side_effect = None  # Reset to use new side_effect below.

    created_task_ids: list[str] = ["task-001"]
    task_counter: list[int] = [2]

    def _create_card(card: object) -> str:
        """Dedup-aware create_card."""
        key = str(card.idempotency_key.value)  # type: ignore[union-attr]
        if key in created_idempotency_keys:
            idx = created_idempotency_keys.index(key)
            return created_task_ids[idx]
        created_idempotency_keys.append(key)
        task_id = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        created_task_ids.append(task_id)
        return task_id

    kanban.create_card.side_effect = _create_card

    run_state = _make_fake_run_state(run, [node_a_record])

    card_result_a = CardResult(
        task_id="task-001",
        event_id=1,
        event_kind="completed",
        summary="Step A done.",
        metadata={},
    )
    event_log = MagicMock()
    event_log.read_since.return_value = [card_result_a]

    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph crash_test {}"
    clock = MagicMock()
    clock.now.return_value = _LATER

    # Simulate gateway restart.
    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
        advance_fn=advance_on_completion,
    )

    # node_a must NOT have been re-dispatched.
    node_a_count = created_idempotency_keys.count(node_a_key.value)
    assert node_a_count == 1, f"node_a was created {node_a_count} times; expected exactly 1"

    # node_b MUST have been dispatched.
    node_b_keys = [k for k in created_idempotency_keys if "node_b" in k]
    assert node_b_keys, "Expected node_b to be dispatched after reconcile"

    # Cursor advanced.
    final_run = run_state._runs[run_id]  # noqa: SLF001
    assert final_run.last_seen_event_id >= 1

    event_log.read_since.assert_called_once_with(0)


def test_reconcile_is_idempotent_when_called_multiple_times() -> None:
    """Calling reconcile twice with the same event log does not double-dispatch cards."""
    pipeline = _make_two_node_pipeline()
    run_id = "idempotent-run"

    run = Run(
        run_id=run_id,
        spec_id="crash_test",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
        last_seen_event_id=0,
    )
    node_a_record = RunNode(
        run_id=run_id,
        node_id="node_a",
        task_id="task-001",
        status=NodeRunStatus.DISPATCHED,
        attempt=1,
        parent_node_ids=["start"],
    )

    _, created_task_ids, created_idempotency_keys = _make_fake_kanban()
    created_idempotency_keys.clear()
    kanban = MagicMock()
    created_idempotency_keys.append("attractor:idempotent-run:node_a:attempt:1")
    task_counter: list[int] = [2]

    def _create_card_idempotent(card: object) -> str:
        """Dedup-aware create_card for idempotency test."""
        key = str(card.idempotency_key.value)  # type: ignore[union-attr]
        if key in created_idempotency_keys:
            idx = created_idempotency_keys.index(key)
            if idx < len(created_task_ids):
                return created_task_ids[idx]
            return "task-001"
        created_idempotency_keys.append(key)
        task_id = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        created_task_ids.append(task_id)
        return task_id

    kanban.create_card.side_effect = _create_card_idempotent
    run_state = _make_fake_run_state(run, [node_a_record])

    card_result_a = CardResult(
        task_id="task-001",
        event_id=1,
        event_kind="completed",
        summary="Step A done.",
        metadata={},
    )
    event_log = MagicMock()
    # First call: unprocessed event; second call: cursor already advanced.
    event_log.read_since.side_effect = [[card_result_a], []]

    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph crash_test {}"
    clock = MagicMock()
    clock.now.return_value = _LATER

    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
        advance_fn=advance_on_completion,
    )
    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
        advance_fn=advance_on_completion,
    )

    node_b_count = sum(1 for k in created_idempotency_keys if "node_b" in k)
    assert node_b_count == 1, f"node_b dispatched {node_b_count} times; expected 1"
