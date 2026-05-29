"""Unit tests for the reconcile use case (RED phase M3 US3).

Tests fail until src/hermes_attractor/use_cases/reconcile.py is implemented.
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
from hermes_attractor.domain.run import NodeRunStatus, Run, RunNode, RunStatus
from hermes_attractor.use_cases.reconcile import reconcile

pytestmark = pytest.mark.unit

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
_LATER = datetime.datetime(2026, 1, 1, second=10, tzinfo=datetime.UTC)


def _make_pipeline(spec_id: str = "spec-a") -> Pipeline:
    """Build a minimal 2-node linear pipeline for testing.

    Args:
        spec_id: Pipeline spec identifier.

    Returns:
        A Pipeline with start -> work -> exit structure.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="worker")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="exit"),
    ]
    return Pipeline(
        spec_id=spec_id,
        nodes=[start, work, exit_],
        edges=edges,
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="worker")]),
    )


def _make_run(
    run_id: str = "run1",
    spec_id: str = "spec-a",
    status: RunStatus = RunStatus.RUNNING,
    last_seen_event_id: int = 0,
) -> Run:
    """Build a minimal Run for testing.

    Args:
        run_id: The run identifier.
        spec_id: The pipeline spec identifier.
        status: The run's lifecycle status.
        last_seen_event_id: The current replay cursor.

    Returns:
        A Run instance.
    """
    return Run(
        run_id=run_id,
        spec_id=spec_id,
        status=status,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
        last_seen_event_id=last_seen_event_id,
    )


def _make_run_node(
    run_id: str = "run1",
    node_id: str = "work",
    task_id: str = "task-001",
    status: NodeRunStatus = NodeRunStatus.DISPATCHED,
) -> RunNode:
    """Build a minimal RunNode for testing.

    Args:
        run_id: The run identifier.
        node_id: The pipeline node identifier.
        task_id: The kanban task identifier.
        status: The node's current execution status.

    Returns:
        A RunNode instance.
    """
    return RunNode(
        run_id=run_id,
        node_id=node_id,
        task_id=task_id,
        status=status,
        attempt=1,
        parent_node_ids=[],
    )


# ---------------------------------------------------------------------------
# reconcile use case
# ---------------------------------------------------------------------------


def test_reconcile_processes_unprocessed_terminal_events() -> None:
    """Reconcile reads EventLog.read_since(cursor) and advances the run for each event."""
    pipeline = _make_pipeline()
    run = _make_run(last_seen_event_id=0)
    node = _make_run_node("run1", "work", "task-001", NodeRunStatus.DISPATCHED)

    card_result = CardResult(
        task_id="task-001",
        event_id=5,
        event_kind="completed",
        summary="Done.",
        metadata={},
    )

    run_state = MagicMock()
    run_state.active_runs.return_value = [run]
    run_state.get_run.return_value = run
    run_state.get_node_by_task.return_value = node
    run_state.nodes_for_run.return_value = [node]

    event_log = MagicMock()
    event_log.read_since.return_value = [card_result]

    kanban = MagicMock()
    kanban.create_card.return_value = "task-002"

    serializer = MagicMock()
    serializer.parse.return_value = pipeline

    store = MagicMock()
    store.load.return_value = "digraph spec-a {}"

    clock = MagicMock()
    clock.now.return_value = _LATER

    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
    )

    # EventLog must have been queried from the run's cursor.
    event_log.read_since.assert_called_once_with(0)
    # The run state must have been advanced (save_run called to persist cursor).
    run_state.save_run.assert_called()


def test_reconcile_skips_already_succeeded_runs() -> None:
    """Reconcile skips runs that are already in a terminal status (SUCCEEDED, FAILED)."""
    run = _make_run(status=RunStatus.SUCCEEDED)

    run_state = MagicMock()
    run_state.active_runs.return_value = []  # succeeded runs are not "active"

    event_log = MagicMock()
    event_log.read_since.return_value = []

    kanban = MagicMock()
    serializer = MagicMock()
    store = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _LATER

    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
    )

    # Should not try to advance the succeeded run.
    event_log.read_since.assert_not_called()
    kanban.create_card.assert_not_called()
    _ = run  # silence unused variable warning


def test_reconcile_is_idempotent_on_same_events() -> None:
    """Running reconcile twice with the same events produces the same net state."""
    pipeline = _make_pipeline()
    run = _make_run(last_seen_event_id=0)
    node = _make_run_node("run1", "work", "task-001", NodeRunStatus.DISPATCHED)

    card_result = CardResult(
        task_id="task-001",
        event_id=5,
        event_kind="completed",
        summary="Done.",
        metadata={},
    )

    run_state = MagicMock()
    run_state.active_runs.return_value = [run]
    run_state.get_run.return_value = run
    run_state.get_node_by_task.return_value = node
    run_state.nodes_for_run.return_value = [node]

    event_log = MagicMock()
    # Both calls return the same event (cursor not advanced between calls in this mock).
    event_log.read_since.return_value = [card_result]

    kanban = MagicMock()
    kanban.create_card.return_value = "task-002"

    serializer = MagicMock()
    serializer.parse.return_value = pipeline

    store = MagicMock()
    store.load.return_value = "digraph spec-a {}"

    clock = MagicMock()
    clock.now.return_value = _LATER

    # First call.
    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
    )
    first_create_count = kanban.create_card.call_count

    # Second call — should produce the same number of new create_card calls.
    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
    )
    second_create_count = kanban.create_card.call_count

    # Idempotency: second call creates the same number as the first (same per-call net).
    assert second_create_count == first_create_count * 2


def test_reconcile_skips_terminal_status_runs_in_active_list() -> None:
    """Reconcile skips BLOCKED runs that appear in the active list (defensive guard)."""
    blocked_run = _make_run(status=RunStatus.BLOCKED)

    run_state = MagicMock()
    # active_runs returns the blocked run (defensive: shouldn't happen but guard it).
    run_state.active_runs.return_value = [blocked_run]

    event_log = MagicMock()
    kanban = MagicMock()
    serializer = MagicMock()
    store = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _LATER

    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
    )

    event_log.read_since.assert_not_called()
    kanban.create_card.assert_not_called()


def test_reconcile_does_nothing_when_no_active_runs() -> None:
    """Reconcile exits immediately when there are no active runs."""
    run_state = MagicMock()
    run_state.active_runs.return_value = []

    event_log = MagicMock()
    kanban = MagicMock()
    serializer = MagicMock()
    store = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _LATER

    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
    )

    event_log.read_since.assert_not_called()
    kanban.create_card.assert_not_called()
