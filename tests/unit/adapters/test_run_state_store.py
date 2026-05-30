"""Unit tests for the RunStateStore port and SQLite adapter (RED phase for M2 US2).

Tests fail until ports/run_state.py and adapters/run_state_store.py are implemented.
"""

from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path  # noqa: TC003  # used in function signatures at runtime

import pytest

from hermes_attractor.adapters.run_state_store import SqliteRunStateStore
from hermes_attractor.domain.pipeline import Context, GoalGatePolicy
from hermes_attractor.domain.run import NodeRunStatus, Run, RunNode, RunStatus
from hermes_attractor.ports.run_state import RunStateStore

pytestmark = pytest.mark.unit

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _make_run(run_id: str = "run1", status: RunStatus = RunStatus.PENDING) -> Run:
    """Build a minimal Run for testing."""
    return Run(
        run_id=run_id,
        spec_id="spec-a",
        status=status,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_run_node(run_id: str = "run1", node_id: str = "work", task_id: str | None = None) -> RunNode:
    """Build a minimal RunNode for testing."""
    return RunNode(
        run_id=run_id,
        node_id=node_id,
        task_id=task_id,
        status=NodeRunStatus.PENDING,
        attempt=1,
        parent_node_ids=[],
    )


# ---------------------------------------------------------------------------
# Protocol surface
# ---------------------------------------------------------------------------


def test_run_state_store_protocol_has_required_methods() -> None:
    """RunStateStore Protocol must declare all required CRUD methods."""
    required_methods = (
        "create_run",
        "get_run",
        "active_runs",
        "save_run",
        "upsert_node",
        "get_node_by_task",
        "nodes_for_run",
    )
    for method in required_methods:
        assert hasattr(RunStateStore, method), f"RunStateStore missing method: {method}"
        assert callable(getattr(RunStateStore, method))


# ---------------------------------------------------------------------------
# SqliteRunStateStore
# ---------------------------------------------------------------------------


def test_create_run_then_get_run_returns_same_run(tmp_path: Path) -> None:
    """SqliteRunStateStore.create_run then get_run returns the same Run."""
    store = SqliteRunStateStore(db_path=tmp_path / "runs.db")
    run = _make_run("r1")
    store.create_run(run)
    fetched = store.get_run("r1")
    assert fetched is not None
    assert fetched.run_id == "r1"
    assert fetched.spec_id == "spec-a"
    assert fetched.status is RunStatus.PENDING
    assert fetched.last_seen_event_id == 0


def test_get_run_returns_none_for_unknown_id(tmp_path: Path) -> None:
    """SqliteRunStateStore.get_run returns None for an unknown run_id."""
    store = SqliteRunStateStore(db_path=tmp_path / "runs.db")
    assert store.get_run("nonexistent") is None


def test_save_run_updates_status_and_event_id(tmp_path: Path) -> None:
    """SqliteRunStateStore.save_run updates the run's status and last_seen_event_id."""
    store = SqliteRunStateStore(db_path=tmp_path / "runs.db")
    run = _make_run("r1")
    store.create_run(run)

    updated = Run(
        run_id="r1",
        spec_id="spec-a",
        status=RunStatus.RUNNING,
        context=Context(data={"x": 1}),
        created_at=_NOW,
        updated_at=_NOW,
        last_seen_event_id=42,
    )
    store.save_run(updated)

    fetched = store.get_run("r1")
    assert fetched is not None
    assert fetched.status is RunStatus.RUNNING
    assert fetched.last_seen_event_id == 42


def test_upsert_node_creates_node(tmp_path: Path) -> None:
    """SqliteRunStateStore.upsert_node creates a new RunNode."""
    store = SqliteRunStateStore(db_path=tmp_path / "runs.db")
    store.create_run(_make_run("r1"))
    node = _make_run_node("r1", "work", task_id="task-001")
    store.upsert_node(node)

    nodes = store.nodes_for_run("r1")
    assert len(nodes) == 1
    assert nodes[0].node_id == "work"
    assert nodes[0].task_id == "task-001"


def test_upsert_node_updates_existing_node(tmp_path: Path) -> None:
    """SqliteRunStateStore.upsert_node updates an existing RunNode."""
    store = SqliteRunStateStore(db_path=tmp_path / "runs.db")
    store.create_run(_make_run("r1"))
    store.upsert_node(_make_run_node("r1", "work"))

    updated_node = RunNode(
        run_id="r1",
        node_id="work",
        task_id="task-abc",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=[],
    )
    store.upsert_node(updated_node)

    nodes = store.nodes_for_run("r1")
    assert len(nodes) == 1
    assert nodes[0].status is NodeRunStatus.RUNNING
    assert nodes[0].task_id == "task-abc"


def test_get_node_by_task_returns_correct_node(tmp_path: Path) -> None:
    """SqliteRunStateStore.get_node_by_task returns the RunNode with the given task_id."""
    store = SqliteRunStateStore(db_path=tmp_path / "runs.db")
    store.create_run(_make_run("r1"))
    store.upsert_node(_make_run_node("r1", "work-a", task_id="task-111"))
    store.upsert_node(_make_run_node("r1", "work-b", task_id="task-222"))

    node = store.get_node_by_task("task-111")
    assert node is not None
    assert node.node_id == "work-a"


def test_get_node_by_task_returns_none_for_unknown_task(tmp_path: Path) -> None:
    """SqliteRunStateStore.get_node_by_task returns None for an unknown task_id."""
    store = SqliteRunStateStore(db_path=tmp_path / "runs.db")
    assert store.get_node_by_task("unknown-task") is None


def test_nodes_for_run_returns_all_nodes_for_run(tmp_path: Path) -> None:
    """SqliteRunStateStore.nodes_for_run returns all nodes for a given run_id."""
    store = SqliteRunStateStore(db_path=tmp_path / "runs.db")
    store.create_run(_make_run("r1"))
    store.upsert_node(_make_run_node("r1", "a"))
    store.upsert_node(_make_run_node("r1", "b"))

    nodes = store.nodes_for_run("r1")
    node_ids = {n.node_id for n in nodes}
    assert node_ids == {"a", "b"}


def test_nodes_for_run_returns_empty_for_unknown_run(tmp_path: Path) -> None:
    """SqliteRunStateStore.nodes_for_run returns an empty sequence for an unknown run_id."""
    store = SqliteRunStateStore(db_path=tmp_path / "runs.db")
    assert list(store.nodes_for_run("unknown")) == []


def test_active_runs_returns_running_and_paused_human_runs(tmp_path: Path) -> None:
    """SqliteRunStateStore.active_runs returns only RUNNING and PAUSED_HUMAN runs."""
    store = SqliteRunStateStore(db_path=tmp_path / "runs.db")
    store.create_run(_make_run("r1", RunStatus.PENDING))
    store.create_run(_make_run("r2", RunStatus.RUNNING))
    store.create_run(_make_run("r3", RunStatus.PAUSED_HUMAN))
    store.create_run(_make_run("r4", RunStatus.SUCCEEDED))
    store.create_run(_make_run("r5", RunStatus.FAILED))

    active = store.active_runs()
    active_ids = {r.run_id for r in active}
    assert active_ids == {"r2", "r3"}


def test_context_data_persisted_and_restored(tmp_path: Path) -> None:
    """SqliteRunStateStore round-trips Run.context data correctly."""
    store = SqliteRunStateStore(db_path=tmp_path / "runs.db")
    run = Run(
        run_id="r1",
        spec_id="spec-a",
        status=RunStatus.PENDING,
        context=Context(data={"key": "value", "num": 42}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    store.create_run(run)
    fetched = store.get_run("r1")
    assert fetched is not None
    assert fetched.context.data == {"key": "value", "num": 42}


def test_upsert_node_with_goal_gate_policy_round_trips(tmp_path: Path) -> None:
    """SqliteRunStateStore round-trips a RunNode's GoalGatePolicy correctly."""
    store = SqliteRunStateStore(db_path=tmp_path / "runs.db")
    store.create_run(_make_run("r1"))
    policy = GoalGatePolicy(retry_target="start", max_attempts=3)
    node = RunNode(
        run_id="r1",
        node_id="gate",
        task_id="task-gate",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["work"],
        goal_gate_policy=policy,
        output_ref="ref://gate/1",
    )
    store.upsert_node(node)

    fetched = store.get_node_by_task("task-gate")
    assert fetched is not None
    assert fetched.goal_gate_policy is not None
    assert fetched.goal_gate_policy.retry_target == "start"
    assert fetched.goal_gate_policy.max_attempts == 3
    assert fetched.output_ref == "ref://gate/1"
    assert list(fetched.parent_node_ids) == ["work"]


# ---------------------------------------------------------------------------
# Non-UTC timestamp deserialization
# ---------------------------------------------------------------------------


def test_get_run_with_non_utc_stored_timestamp_converts_correctly(tmp_path: Path) -> None:
    """get_run correctly converts a non-UTC offset timestamp stored in the DB.

    ``2026-05-01T12:00:00+05:00`` is 07:00 UTC, not 12:00 UTC.
    The old ``replace(tzinfo=UTC)`` would silently return 12:00 UTC (wrong);
    ``astimezone(UTC)`` returns the correct 07:00 UTC moment.
    """
    db_path = tmp_path / "runs.db"
    store = SqliteRunStateStore(db_path=db_path)
    store.create_run(_make_run("r1"))

    # Directly patch the stored timestamp to a non-UTC offset string.
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        _ = conn.execute(
            "UPDATE plugin_runs SET created_at = ?, updated_at = ? WHERE run_id = ?",
            ("2026-05-01T12:00:00+05:00", "2026-05-01T12:00:00+05:00", "r1"),
        )
        conn.commit()

    fetched = store.get_run("r1")
    assert fetched is not None
    expected_utc = datetime.datetime(2026, 5, 1, 7, 0, 0, tzinfo=datetime.UTC)
    assert fetched.created_at == expected_utc
    assert fetched.updated_at == expected_utc
