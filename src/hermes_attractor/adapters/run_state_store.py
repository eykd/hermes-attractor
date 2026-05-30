"""SQLite-backed RunStateStore adapter with WAL mode and idempotent-replay ordering.

Schema: ``plugin_runs`` + ``plugin_run_nodes``.
WAL mode and a 5-second busy_timeout prevent hard lock failures under
concurrent read access.

See: specs/001-attractor-kanban/contracts/ports.md §RunStateStore
See: specs/001-attractor-kanban/plan.md §Edge Cases §SQLite multi-process
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003  # Path used in runtime annotation
from typing import TYPE_CHECKING

from hermes_attractor.domain.pipeline import Context, GoalGatePolicy
from hermes_attractor.domain.run import NodeRunStatus, Run, RunNode, RunStatus

if TYPE_CHECKING:
    from collections.abc import Sequence

_log = logging.getLogger(__name__)

#: DDL that creates the run-state schema and configures WAL + busy_timeout.
#: Idempotent (IF NOT EXISTS); safe to run on every connection open.
_DDL = """\
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS plugin_runs (
    run_id              TEXT PRIMARY KEY,
    spec_id             TEXT NOT NULL,
    status              TEXT NOT NULL,
    root_task_id        TEXT,
    last_seen_event_id  INTEGER NOT NULL DEFAULT 0,
    context_json        TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plugin_run_nodes (
    run_id              TEXT NOT NULL,
    node_id             TEXT NOT NULL,
    attempt             INTEGER NOT NULL DEFAULT 1,
    task_id             TEXT,
    status              TEXT NOT NULL,
    parent_node_ids_json     TEXT NOT NULL DEFAULT '[]',
    goal_gate_policy_json    TEXT,
    output_ref          TEXT,
    context_updates_json     TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (run_id, node_id, attempt)
);

CREATE INDEX IF NOT EXISTS idx_run_nodes_task_id
    ON plugin_run_nodes(task_id);

CREATE INDEX IF NOT EXISTS idx_run_nodes_run_id
    ON plugin_run_nodes(run_id);
"""

_ACTIVE_STATUSES = (RunStatus.RUNNING.value, RunStatus.PAUSED_HUMAN.value)


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a WAL-mode SQLite connection and ensure the schema exists.

    Args:
        db_path: Filesystem path to the SQLite database file.

    Returns:
        An open ``sqlite3.Connection`` with row_factory set to ``sqlite3.Row``.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _ = conn.executescript(_DDL)
    conn.commit()
    return conn


def _dt_to_str(dt: datetime) -> str:
    """Serialise a datetime to an ISO-8601 UTC string.

    Args:
        dt: A timezone-aware datetime.

    Returns:
        ISO-8601 string in UTC.
    """
    return dt.astimezone(UTC).isoformat()


def _str_to_dt(s: str) -> datetime:
    """Deserialise an ISO-8601 UTC string to a timezone-aware datetime.

    Args:
        s: ISO-8601 UTC string.

    Returns:
        A timezone-aware ``datetime`` in UTC.
    """
    return datetime.fromisoformat(s).astimezone(UTC)


def _goal_gate_to_json(policy: GoalGatePolicy | None) -> str | None:
    """Serialise a GoalGatePolicy to JSON, or return None.

    Args:
        policy: The GoalGatePolicy to serialise, or ``None``.

    Returns:
        A JSON string, or ``None`` if policy is ``None``.
    """
    if policy is None:
        return None
    return json.dumps({"retry_target": policy.retry_target, "max_attempts": policy.max_attempts})


def _json_to_goal_gate(s: str | None) -> GoalGatePolicy | None:
    """Deserialise a JSON string to a GoalGatePolicy, or return None.

    Args:
        s: JSON string, or ``None``.

    Returns:
        A GoalGatePolicy, or ``None``.
    """
    if s is None:
        return None
    data = json.loads(s)
    return GoalGatePolicy(retry_target=data["retry_target"], max_attempts=data["max_attempts"])


def _row_to_run(row: sqlite3.Row) -> Run:
    """Convert a ``plugin_runs`` row to a Run domain object.

    Args:
        row: A ``sqlite3.Row`` from the ``plugin_runs`` table.

    Returns:
        The corresponding Run.
    """
    return Run(
        run_id=row["run_id"],
        spec_id=row["spec_id"],
        status=RunStatus(row["status"]),
        root_task_id=row["root_task_id"],
        last_seen_event_id=int(row["last_seen_event_id"]),
        context=Context(data=json.loads(row["context_json"])),
        created_at=_str_to_dt(row["created_at"]),
        updated_at=_str_to_dt(row["updated_at"]),
    )


def _row_to_run_node(row: sqlite3.Row) -> RunNode:
    """Convert a ``plugin_run_nodes`` row to a RunNode domain object.

    Args:
        row: A ``sqlite3.Row`` from the ``plugin_run_nodes`` table.

    Returns:
        The corresponding RunNode.
    """
    raw_cu = row["context_updates_json"]
    context_updates: dict[str, object] = json.loads(raw_cu) if raw_cu else {}
    return RunNode(
        run_id=row["run_id"],
        node_id=row["node_id"],
        attempt=int(row["attempt"]),
        task_id=row["task_id"],
        status=NodeRunStatus(row["status"]),
        parent_node_ids=json.loads(row["parent_node_ids_json"]),
        goal_gate_policy=_json_to_goal_gate(row["goal_gate_policy_json"]),
        output_ref=row["output_ref"],
        context_updates=context_updates,
    )


class SqliteRunStateStore:
    """SQLite-backed RunStateStore with WAL mode and 5-second busy_timeout.

    Uses a per-call connection to remain process-safe under SQLite's WAL reader
    concurrency model (plan.md §Edge Cases §SQLite multi-process).

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialise the store and ensure the schema is created.

        Args:
            db_path: Filesystem path to the SQLite database file (created if absent).
        """
        super().__init__()
        self.db_path = db_path
        # Eagerly create schema on construction.
        conn = _connect(db_path)
        conn.close()

    def create_run(self, run: Run) -> None:
        """Insert a new Run record.

        Args:
            run: The Run to persist.
        """
        with _connect(self.db_path) as conn:
            _ = conn.execute(
                """
                INSERT INTO plugin_runs
                    (run_id, spec_id, status, root_task_id, last_seen_event_id,
                     context_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.spec_id,
                    run.status.value,
                    run.root_task_id,
                    run.last_seen_event_id,
                    json.dumps(dict(run.context.data)),
                    _dt_to_str(run.created_at),
                    _dt_to_str(run.updated_at),
                ),
            )

    def get_run(self, run_id: str) -> Run | None:
        """Fetch a Run by its run_id.

        Args:
            run_id: The unique run identifier.

        Returns:
            The Run if found, else ``None``.
        """
        with _connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM plugin_runs WHERE run_id = ?", (run_id,)).fetchone()
        return _row_to_run(row) if row else None

    def active_runs(self) -> Sequence[Run]:
        """Return all Runs in RUNNING or PAUSED_HUMAN status.

        Returns:
            A sequence of active Run records.
        """
        placeholders = ",".join("?" for _ in _ACTIVE_STATUSES)
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM plugin_runs WHERE status IN ({placeholders})",  # noqa: S608
                _ACTIVE_STATUSES,
            ).fetchall()
        return [_row_to_run(row) for row in rows]

    def save_run(self, run: Run) -> None:
        """Update an existing Run — last_seen_event_id cursor update is the final write.

        Per FR-024 contract: the cursor update must be the last write so a
        mid-advance crash causes event re-processing on replay.

        Args:
            run: The updated Run to persist.
        """
        with _connect(self.db_path) as conn:
            _ = conn.execute(
                """
                UPDATE plugin_runs
                SET spec_id=?, status=?, root_task_id=?, context_json=?,
                    updated_at=?, last_seen_event_id=?
                WHERE run_id=?
                """,
                (
                    run.spec_id,
                    run.status.value,
                    run.root_task_id,
                    json.dumps(dict(run.context.data)),
                    _dt_to_str(run.updated_at),
                    run.last_seen_event_id,
                    run.run_id,
                ),
            )

    def upsert_node(self, node: RunNode) -> None:
        """Create or update a RunNode (keyed on run_id + node_id + attempt).

        Args:
            node: The RunNode to create or update.
        """
        with _connect(self.db_path) as conn:
            _ = conn.execute(
                """
                INSERT INTO plugin_run_nodes
                    (run_id, node_id, attempt, task_id, status,
                     parent_node_ids_json, goal_gate_policy_json, output_ref,
                     context_updates_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, node_id, attempt) DO UPDATE SET
                    task_id=excluded.task_id,
                    status=excluded.status,
                    parent_node_ids_json=excluded.parent_node_ids_json,
                    goal_gate_policy_json=excluded.goal_gate_policy_json,
                    output_ref=excluded.output_ref,
                    context_updates_json=excluded.context_updates_json
                """,
                (
                    node.run_id,
                    node.node_id,
                    node.attempt,
                    node.task_id,
                    node.status.value,
                    json.dumps(list(node.parent_node_ids)),
                    _goal_gate_to_json(node.goal_gate_policy),
                    node.output_ref,
                    json.dumps(dict(node.context_updates)),
                ),
            )

    def get_node_by_task(self, task_id: str) -> RunNode | None:
        """Fetch the RunNode associated with a given kanban task_id.

        Args:
            task_id: The kanban task identifier.

        Returns:
            The RunNode if found, else ``None``.
        """
        with _connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM plugin_run_nodes WHERE task_id = ?", (task_id,)).fetchone()
        return _row_to_run_node(row) if row else None

    def nodes_for_run(self, run_id: str) -> Sequence[RunNode]:
        """Return all RunNode records for a given run_id.

        Args:
            run_id: The run identifier.

        Returns:
            A sequence of RunNode records, possibly empty.
        """
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM plugin_run_nodes WHERE run_id = ? ORDER BY node_id, attempt",
                (run_id,),
            ).fetchall()
        return [_row_to_run_node(row) for row in rows]
