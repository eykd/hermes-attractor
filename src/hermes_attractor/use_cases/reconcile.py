"""Reconcile use case: replay unprocessed events for active runs.

Called on ``on_session_start`` and via the ``attractor reconcile`` CLI command.
Reads the EventLog since the last-seen cursor for each active run, advances
the state machine for any unprocessed terminal events, and persists the cursor
last (FR-024 cursor-last ordering, idempotent replay).

Design invariants:
  - Terminal runs (SUCCEEDED / FAILED / BLOCKED) are skipped.
  - The event cursor is advanced AFTER follow-up cards are created, ensuring
    a crash mid-batch re-processes the incomplete batch on the next reconcile.
  - Running reconcile twice with the same event log produces the same net state
    (idempotency via card idempotency keys + upsert_node semantics).

See: specs/001-attractor-kanban/contracts/tools.md §CLI command
See: specs/001-attractor-kanban/plan.md §M3, §Edge Cases §Concurrent advancement
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hermes_attractor.domain.run import RunStatus
from hermes_attractor.use_cases.run_execution import advance_on_completion

if TYPE_CHECKING:
    from hermes_attractor.ports.clock import Clock
    from hermes_attractor.ports.dot import DotSerializer
    from hermes_attractor.ports.event_log import EventLog
    from hermes_attractor.ports.kanban import KanbanBoard
    from hermes_attractor.ports.pipeline_store import PipelineStore
    from hermes_attractor.ports.run_state import RunStateStore

_log = logging.getLogger(__name__)

#: Statuses that indicate a run is no longer active.
_TERMINAL_STATUSES: frozenset[RunStatus] = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.BLOCKED})


def reconcile(  # noqa: PLR0913
    *,
    run_state: RunStateStore,
    event_log: EventLog,
    serializer: DotSerializer,
    store: PipelineStore,
    kanban: KanbanBoard,
    clock: Clock,
) -> None:
    """Replay unprocessed terminal events for all active runs.

    For each active run:
    1. Read events from the EventLog since the run's ``last_seen_event_id``.
    2. For each unprocessed terminal event, call ``advance_on_completion``.
    3. ``advance_on_completion`` persists the cursor as its last write (FR-024).

    Args:
        run_state: The RunStateStore port for reading and persisting run state.
        event_log: The EventLog port for reading terminal kanban events.
        serializer: The DotSerializer port for parsing pipeline DOT.
        store: The PipelineStore port for loading pipeline DOT.
        kanban: The KanbanBoard port for creating follow-up cards.
        clock: The Clock port for timestamps.
    """
    active_runs = run_state.active_runs()
    if not active_runs:
        return

    for run in active_runs:
        if run.status in _TERMINAL_STATUSES:
            _log.debug("reconcile: skipping terminal run %s (status=%s)", run.run_id, run.status)
            continue

        _reconcile_run(
            last_seen_event_id=run.last_seen_event_id,
            spec_id=run.spec_id,
            run_state=run_state,
            event_log=event_log,
            serializer=serializer,
            store=store,
            kanban=kanban,
            clock=clock,
        )


def _reconcile_run(  # noqa: PLR0913
    *,
    last_seen_event_id: int,
    spec_id: str,
    run_state: RunStateStore,
    event_log: EventLog,
    serializer: DotSerializer,
    store: PipelineStore,
    kanban: KanbanBoard,
    clock: Clock,
) -> None:
    """Process all unprocessed events for a single run.

    Reads the EventLog from the cursor and advances the run for each event.
    The cursor is advanced atomically by ``advance_on_completion`` as its last write.

    Args:
        last_seen_event_id: The current replay cursor for this run.
        spec_id: The pipeline spec identifier (for loading the DOT).
        run_state: The RunStateStore port.
        event_log: The EventLog port.
        serializer: The DotSerializer port.
        store: The PipelineStore port.
        kanban: The KanbanBoard port.
        clock: The Clock port.
    """
    events = event_log.read_since(last_seen_event_id)
    if not events:
        return

    # Load the pipeline once for this run's batch.
    dot = store.load(spec_id)
    pipeline = serializer.parse(dot)

    for card_result in events:
        advance_on_completion(
            card_result=card_result,
            kanban=kanban,
            run_state=run_state,
            pipeline=pipeline,
            clock=clock,
        )
