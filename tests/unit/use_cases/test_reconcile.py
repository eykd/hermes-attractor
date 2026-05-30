"""Unit tests for the reconcile use case (RED phase M3 US3).

Tests fail until src/hermes_attractor/use_cases/reconcile.py is implemented.
"""

from __future__ import annotations

import dataclasses
import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence

from hermes_attractor.domain.card import CardResult
from hermes_attractor.domain.constants import EVENT_LOG_BATCH_SIZE
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
from hermes_attractor.use_cases.run_execution import advance_on_completion

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
        advance_fn=advance_on_completion,
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
        advance_fn=advance_on_completion,
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
        advance_fn=advance_on_completion,
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
        advance_fn=advance_on_completion,
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
        advance_fn=advance_on_completion,
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
        advance_fn=advance_on_completion,
    )

    event_log.read_since.assert_not_called()
    kanban.create_card.assert_not_called()


def test_reconcile_run_does_nothing_when_events_empty() -> None:
    """Reconcile skips pipeline load and advance when event_log.read_since returns []."""
    run = _make_run(last_seen_event_id=42)

    run_state = MagicMock()
    run_state.active_runs.return_value = [run]
    run_state.get_run.return_value = run

    event_log = MagicMock()
    # Active run but no new events since cursor 42.
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
        advance_fn=advance_on_completion,
    )

    event_log.read_since.assert_called_once_with(42)
    # Pipeline must NOT be loaded when there are no events to process.
    store.load.assert_not_called()
    kanban.create_card.assert_not_called()


def test_reconcile_scopes_events_to_owning_run() -> None:
    """Each terminal event is advanced only against its owning run, not any other run.

    Two concurrent active runs (run-A and run-B) with interleaved events:
    - event_id=1 belongs to run-A (task-A1)
    - event_id=2 belongs to run-B (task-B1)
    - event_id=3 belongs to run-A (task-A2)

    Assertions:
    - run-A's advance_fn is called exactly for events 1 and 3 (not 2).
    - run-B's advance_fn is called exactly for event 2 (not 1 or 3).
    - The cursor re-read via get_run is used instead of the snapshot.
    """
    pipeline_a = _make_pipeline(spec_id="spec-a")
    pipeline_b = _make_pipeline(spec_id="spec-b")

    run_a = _make_run(run_id="run-a", spec_id="spec-a", last_seen_event_id=0)
    run_b = _make_run(run_id="run-b", spec_id="spec-b", last_seen_event_id=0)

    node_a1 = _make_run_node(run_id="run-a", node_id="work", task_id="task-A1")
    node_a2 = _make_run_node(run_id="run-a", node_id="work", task_id="task-A2")
    node_b1 = _make_run_node(run_id="run-b", node_id="work", task_id="task-B1")

    event_a1 = CardResult(task_id="task-A1", event_id=1, event_kind="completed", summary="A1", metadata={})
    event_b1 = CardResult(task_id="task-B1", event_id=2, event_kind="completed", summary="B1", metadata={})
    event_a2 = CardResult(task_id="task-A2", event_id=3, event_kind="completed", summary="A2", metadata={})

    # All three events appear in the global event log since cursor=0.
    all_events = [event_a1, event_b1, event_a2]

    run_state = MagicMock()
    run_state.active_runs.return_value = [run_a, run_b]

    # get_run always returns the fresh run (cursor unchanged for this test).
    def _get_run(run_id: str) -> Run:
        """Return run_a for run-a, run_b for anything else."""
        return run_a if run_id == "run-a" else run_b

    # get_node_by_task resolves each task to its owning run's node.
    def _get_node_by_task(task_id: str) -> RunNode | None:
        """Return the RunNode for the given task_id."""
        return {
            "task-A1": node_a1,
            "task-A2": node_a2,
            "task-B1": node_b1,
        }.get(task_id)

    run_state.get_run.side_effect = _get_run
    run_state.get_node_by_task.side_effect = _get_node_by_task
    run_state.nodes_for_run.return_value = []

    event_log = MagicMock()
    event_log.read_since.return_value = all_events

    kanban = MagicMock()
    kanban.create_card.return_value = "task-next"

    serializer = MagicMock()

    def _parse(dot: str) -> Pipeline:
        """Return pipeline_a if spec-a appears in the dot string, else pipeline_b."""
        return pipeline_a if "spec-a" in dot else pipeline_b

    store = MagicMock()

    def _load(spec_id: str) -> str:
        """Return a stub DOT string encoding the spec_id."""
        return f"digraph {spec_id} {{}}"

    serializer.parse.side_effect = _parse
    store.load.side_effect = _load

    clock = MagicMock()
    clock.now.return_value = _LATER

    # Track which card_results are passed to advance_fn and for which run's pipeline.
    advance_calls: list[tuple[str, str]] = []  # (task_id, pipeline.spec_id)

    def _tracking_advance_fn(
        *,
        card_result: CardResult,
        kanban: object,
        run_state: object,
        pipeline: Pipeline,
        clock: object,
    ) -> None:
        """Record which (task_id, pipeline.spec_id) pairs are advanced."""
        advance_calls.append((card_result.task_id, pipeline.spec_id))

    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
        advance_fn=_tracking_advance_fn,
    )

    # Each event must be advanced against the pipeline of its OWNING run.
    assert ("task-A1", "spec-a") in advance_calls, "event for run-A must use run-A's pipeline"
    assert ("task-A2", "spec-a") in advance_calls, "second run-A event must use run-A's pipeline"
    assert ("task-B1", "spec-b") in advance_calls, "event for run-B must use run-B's pipeline"

    # run-A events must NOT be advanced against run-B's pipeline and vice-versa.
    assert ("task-A1", "spec-b") not in advance_calls, "run-A event must not use run-B's pipeline"
    assert ("task-A2", "spec-b") not in advance_calls, "run-A event must not use run-B's pipeline"
    assert ("task-B1", "spec-a") not in advance_calls, "run-B event must not use run-A's pipeline"

    # Each event must be advanced exactly once in total.
    assert advance_calls.count(("task-A1", "spec-a")) == 1, "task-A1 advanced exactly once"
    assert advance_calls.count(("task-A2", "spec-a")) == 1, "task-A2 advanced exactly once"
    assert advance_calls.count(("task-B1", "spec-b")) == 1, "task-B1 advanced exactly once"

    # get_run must be called to re-read each run's current cursor (not trust snapshot).
    run_state.get_run.assert_called()


def test_reconcile_skips_run_that_disappeared_after_snapshot() -> None:
    """Reconcile skips a run whose get_run returns None after active_runs() listed it."""
    run = _make_run(run_id="vanished", status=RunStatus.RUNNING)

    run_state = MagicMock()
    run_state.active_runs.return_value = [run]
    # Simulate the run having been deleted between active_runs() and get_run().
    run_state.get_run.return_value = None

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
        advance_fn=advance_on_completion,
    )

    # The disappeared run must not trigger any event processing.
    event_log.read_since.assert_not_called()
    kanban.create_card.assert_not_called()


def test_reconcile_skips_run_that_became_terminal_after_snapshot() -> None:
    """Reconcile skips a run that transitioned to terminal between snapshot and re-read.

    active_runs() lists a RUNNING run, but by the time get_run() is called it has
    been marked SUCCEEDED (e.g., advanced by another process). Reconcile must not
    process any events for it.
    """
    snapshot_run = _make_run(run_id="run-concurrent", status=RunStatus.RUNNING)
    current_run = _make_run(run_id="run-concurrent", status=RunStatus.SUCCEEDED)

    run_state = MagicMock()
    run_state.active_runs.return_value = [snapshot_run]
    run_state.get_run.return_value = current_run  # re-read shows terminal status

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
        advance_fn=advance_on_completion,
    )

    event_log.read_since.assert_not_called()
    kanban.create_card.assert_not_called()


def test_reconcile_skips_events_that_belong_to_other_runs() -> None:
    """Reconcile does not advance a run when all events in the log belong to other runs.

    A single active run-A exists. The event log contains only events for run-B.
    After read_since returns events, none of them are owned by run-A (resolved
    via get_node_by_task), so the pipeline is never loaded and advance_fn is never
    called for run-A.
    """
    run_a = _make_run(run_id="run-a", spec_id="spec-a", last_seen_event_id=0)
    node_b = _make_run_node(run_id="run-b", node_id="work", task_id="task-B1")

    event_for_b = CardResult(task_id="task-B1", event_id=7, event_kind="completed", summary="B done", metadata={})

    run_state = MagicMock()
    run_state.active_runs.return_value = [run_a]
    run_state.get_run.return_value = run_a
    run_state.get_node_by_task.return_value = node_b  # resolves to run-B, not run-A

    event_log = MagicMock()
    event_log.read_since.return_value = [event_for_b]

    kanban = MagicMock()
    serializer = MagicMock()
    store = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _LATER

    advance_calls: list[str] = []

    def _noop_advance(**kwargs: object) -> None:
        """Record any advance call (should never be called here)."""
        result = kwargs.get("card_result")
        if hasattr(result, "task_id"):
            advance_calls.append(str(result.task_id))  # type: ignore[union-attr]

    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
        advance_fn=_noop_advance,
    )

    # No events belong to run-A, so pipeline should never be loaded.
    store.load.assert_not_called()
    assert advance_calls == [], "advance_fn must not be called for foreign-run events"


def test_reconcile_processes_all_events_when_backlog_exceeds_one_batch() -> None:
    """_reconcile_run loops over multiple batches when the event backlog > EVENT_LOG_BATCH_SIZE.

    The plan spec (plan.md §Bounded event-log replay) requires looping in bounded
    batches of EVENT_LOG_BATCH_SIZE events, advancing the cursor after each batch.
    This test verifies that a backlog of EVENT_LOG_BATCH_SIZE + 50 events (150 total)
    is fully processed in a single ``reconcile`` call — i.e. that _reconcile_run
    does NOT stop after the first batch of 100.

    Setup:
    - One active run with cursor at 0.
    - event_log.read_since is a stateful fake:
        * First call (cursor=0): returns events 1-100 (full batch of EVENT_LOG_BATCH_SIZE).
        * Second call (cursor=100): returns events 101-150 (partial batch, 50 events).
        * Third call (cursor=150): returns [] (no more events — loop termination).
    - Each event has a unique task_id, and get_node_by_task maps it to the run.
    - advance_fn is a spy that tracks call count.

    Assertion: advance_fn is called exactly EVENT_LOG_BATCH_SIZE + 50 = 150 times,
    proving that all events from the tail batch were processed.
    """
    pipeline = _make_pipeline()
    run = _make_run(last_seen_event_id=0)

    # Build 150 events: IDs 1..150, each with a unique task_id.
    total_events = EVENT_LOG_BATCH_SIZE + 50  # 150
    all_events: list[CardResult] = [
        CardResult(
            task_id=f"task-{i:04d}",
            event_id=i,
            event_kind="completed",
            summary=f"Done {i}",
            metadata={},
        )
        for i in range(1, total_events + 1)
    ]
    batch_1 = all_events[:EVENT_LOG_BATCH_SIZE]  # events 1..100
    batch_2 = all_events[EVENT_LOG_BATCH_SIZE:]  # events 101..150
    assert len(batch_1) == EVENT_LOG_BATCH_SIZE
    assert len(batch_2) == 50

    # Map every task_id to a RunNode owned by run1.
    task_id_to_node: dict[str, RunNode] = {
        event.task_id: _make_run_node(run_id="run1", node_id="work", task_id=event.task_id) for event in all_events
    }

    run_state = MagicMock()
    run_state.active_runs.return_value = [run]

    # get_run returns the run object; updated cursor is stored via save_run.
    # For the loop to re-read the cursor it needs get_run to return the updated run.
    # We simulate the advancing cursor by tracking the last saved run.
    saved_run_ref: list[Run] = [run]

    def _get_run(run_id: str) -> Run:
        """Return the most recently saved version of the run."""
        return saved_run_ref[0]

    def _save_run(r: Run) -> None:
        """Update the saved run reference so the loop sees the new cursor."""
        saved_run_ref[0] = r

    run_state.get_run.side_effect = _get_run
    run_state.save_run.side_effect = _save_run
    run_state.get_node_by_task.side_effect = task_id_to_node.get
    run_state.nodes_for_run.return_value = list(task_id_to_node.values())

    # Stateful fake: returns batch_1 then batch_2 then [] based on cursor.
    def _read_since(last_seen_event_id: int) -> Sequence[CardResult]:
        """Return the appropriate batch for the given cursor position."""
        if last_seen_event_id < EVENT_LOG_BATCH_SIZE:
            return batch_1
        if last_seen_event_id < total_events:
            return batch_2
        return []

    event_log = MagicMock()
    event_log.read_since.side_effect = _read_since

    kanban = MagicMock()
    kanban.create_card.return_value = "task-next"

    serializer = MagicMock()
    serializer.parse.return_value = pipeline

    store = MagicMock()
    store.load.return_value = "digraph spec-a {}"

    clock = MagicMock()
    clock.now.return_value = _LATER

    advance_call_count: list[int] = [0]

    def _counting_advance_fn(
        *,
        card_result: CardResult,
        kanban: object,
        run_state: object,
        pipeline: Pipeline,
        clock: object,
    ) -> None:
        """Count advance calls and update the run cursor to simulate real advance."""
        advance_call_count[0] += 1
        # Simulate cursor advancement: update saved_run_ref with new last_seen_event_id.
        current = saved_run_ref[0]
        updated = dataclasses.replace(current, last_seen_event_id=card_result.event_id)
        saved_run_ref[0] = updated

    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
        advance_fn=_counting_advance_fn,
    )

    assert advance_call_count[0] == total_events, (
        f"Expected advance_fn to be called {total_events} times (all events), "
        f"but was called {advance_call_count[0]} times. "
        f"Events in tail batch (IDs {EVENT_LOG_BATCH_SIZE + 1}-{total_events}) "
        f"are silently dropped when _reconcile_run reads only one batch."
    )


def test_reconcile_stops_batch_loop_gracefully_when_run_disappears_mid_loop() -> None:
    """_reconcile_run stops gracefully if the run disappears between batches.

    When a full batch is returned (suggesting more events remain), the loop
    re-reads the cursor via get_run. If the run has been deleted between the
    first batch and the cursor re-read, _reconcile_run must stop without
    raising and without calling advance_fn a second time.

    Setup:
    - One active run with cursor at 0.
    - First call to read_since returns a full batch (EVENT_LOG_BATCH_SIZE events).
    - get_run returns the run for the initial re-read, then None on the second
      call (simulating deletion mid-loop).
    - advance_fn is a spy.

    Assertion: advance_fn is called exactly EVENT_LOG_BATCH_SIZE times (first
    batch only), and the function returns normally (no exception raised).
    """
    pipeline = _make_pipeline()
    run = _make_run(last_seen_event_id=0)

    full_batch: list[CardResult] = [
        CardResult(
            task_id=f"task-{i:04d}",
            event_id=i,
            event_kind="completed",
            summary=f"Done {i}",
            metadata={},
        )
        for i in range(1, EVENT_LOG_BATCH_SIZE + 1)
    ]

    task_id_to_node: dict[str, RunNode] = {
        event.task_id: _make_run_node(run_id="run1", node_id="work", task_id=event.task_id) for event in full_batch
    }

    # get_run: first call returns run (initial snapshot re-read in reconcile()),
    # second call (after first batch for cursor re-read) returns None.
    get_run_calls: list[int] = [0]

    def _get_run(run_id: str) -> Run | None:
        """Return run on first call, None on second (simulating deletion)."""
        get_run_calls[0] += 1
        if get_run_calls[0] <= 1:
            return run
        return None

    run_state = MagicMock()
    run_state.active_runs.return_value = [run]
    run_state.get_run.side_effect = _get_run
    run_state.get_node_by_task.side_effect = task_id_to_node.get
    run_state.nodes_for_run.return_value = list(task_id_to_node.values())

    # Only one batch returned; second call would return [] but should never be reached.
    event_log = MagicMock()
    event_log.read_since.return_value = full_batch

    kanban = MagicMock()
    kanban.create_card.return_value = "task-next"

    serializer = MagicMock()
    serializer.parse.return_value = pipeline

    store = MagicMock()
    store.load.return_value = "digraph spec-a {}"

    clock = MagicMock()
    clock.now.return_value = _LATER

    advance_call_count: list[int] = [0]

    def _counting_advance_fn(
        *,
        card_result: CardResult,
        kanban: object,
        run_state: object,
        pipeline: Pipeline,
        clock: object,
    ) -> None:
        """Count advance calls."""
        advance_call_count[0] += 1

    # Must not raise even though the run disappears after the first batch.
    reconcile(
        run_state=run_state,
        event_log=event_log,
        serializer=serializer,
        store=store,
        kanban=kanban,
        clock=clock,
        advance_fn=_counting_advance_fn,
    )

    assert advance_call_count[0] == EVENT_LOG_BATCH_SIZE, (
        f"Expected advance_fn called {EVENT_LOG_BATCH_SIZE} times for the first batch, "
        f"but was called {advance_call_count[0]} times."
    )
