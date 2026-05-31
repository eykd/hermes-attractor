"""Unit tests for the reconcile wiring core (``plugin.reconcile.run_reconcile``).

These cover the composition root with injected fakes (fully covered without hermes) and
the env-based default-construction branches (empty run-state store → reconcile is a no-op).
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.pipeline import Context
from hermes_attractor.domain.run import NodeRunStatus, Run, RunNode, RunStatus
from hermes_attractor.plugin.reconcile import run_reconcile

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _make_run() -> Run:
    """Build a minimal active Run for testing.

    Returns:
        A RUNNING Run with cursor at 0.
    """
    return Run(
        run_id="run1",
        spec_id="spec-a",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
        last_seen_event_id=0,
    )


def _make_node(task_id: str) -> RunNode:
    """Build a RunNode owned by run1 for the given task id.

    Args:
        task_id: The kanban task id the node was dispatched as.

    Returns:
        A DISPATCHED RunNode for run1.
    """
    return RunNode(
        run_id="run1",
        node_id="work",
        task_id=task_id,
        status=NodeRunStatus.DISPATCHED,
        attempt=1,
        parent_node_ids=[],
    )


def test_run_reconcile_drives_advance_fn_for_owned_completion() -> None:
    """run_reconcile reads the completion event and calls advance_fn for the owning run."""
    run = _make_run()
    node = _make_node("task-001")
    run_state = MagicMock()
    run_state.active_runs.return_value = [run]
    run_state.get_run.return_value = run
    run_state.get_node_by_task.return_value = node

    reader = MagicMock()
    reader.read_terminal_events.return_value = [
        {"task_id": "task-001", "event_id": 5, "kind": "completed", "summary": "done", "metadata": {}}
    ]

    serializer = MagicMock()
    serializer.parse.return_value = MagicMock(name="pipeline")
    store = MagicMock()
    store.load.return_value = "digraph spec_a {}"
    clock = MagicMock()
    clock.now.return_value = _NOW
    advance_fn = MagicMock()

    run_reconcile(
        tool_client=MagicMock(),
        event_reader=reader,
        run_state=run_state,
        store=store,
        serializer=serializer,
        clock=clock,
        advance_fn=advance_fn,
    )

    advance_fn.assert_called_once()
    _, kwargs = advance_fn.call_args
    assert kwargs["card_result"].task_id == "task-001"
    assert kwargs["card_result"].event_id == 5


def test_run_reconcile_builds_env_defaults_and_noops_on_empty_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no overrides, run_reconcile builds env-based stores; an empty store is a no-op."""
    monkeypatch.setenv("ATTRACTOR_DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.setenv("ATTRACTOR_REPO_BASE", str(tmp_path))

    reader = MagicMock()

    # No run_state/store/serializer/clock/advance_fn → defaults are constructed.
    # The freshly-created run-state DB has no active runs, so reconcile returns early
    # and the event reader is never consulted.
    run_reconcile(tool_client=MagicMock(), event_reader=reader)

    reader.read_terminal_events.assert_not_called()
