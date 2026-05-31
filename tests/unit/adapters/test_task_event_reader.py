"""Unit tests for SqliteTaskEventReader.

Exercise the reader against a plain stdlib sqlite database mirroring the kanban
``task_events`` / ``task_runs`` schema — no hermes_cli import required. The connection
factory is injected, so these tests cover the full SQL JOIN read and metadata parsing.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from hermes_attractor.adapters.task_event_reader import SqliteTaskEventReader

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = pytest.mark.unit

_SCHEMA = """
CREATE TABLE task_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    TEXT NOT NULL,
    run_id     INTEGER,
    kind       TEXT NOT NULL,
    payload    TEXT,
    created_at INTEGER NOT NULL
);
CREATE TABLE task_runs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id  TEXT NOT NULL,
    status   TEXT NOT NULL,
    outcome  TEXT,
    summary  TEXT,
    metadata TEXT
);
"""


def _factory(db_path: Path) -> Callable[[], sqlite3.Connection]:
    """Return a zero-argument connection factory for the given sqlite path.

    Args:
        db_path: Path to the sqlite database file.

    Returns:
        A callable opening a fresh connection to ``db_path``.
    """
    return lambda: sqlite3.connect(str(db_path))


def _init_db(db_path: Path) -> None:
    """Create the minimal kanban schema at ``db_path``.

    Args:
        db_path: Path to the sqlite database file to create.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        _ = conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _insert_run(db_path: Path, *, run_id: int, task_id: str, summary: str | None, metadata: str | None) -> None:
    """Insert a task_runs row.

    Args:
        db_path: Path to the sqlite database file.
        run_id: The run row id.
        task_id: The owning task id.
        summary: The run summary (or None).
        metadata: The run metadata JSON text (or None).
    """
    conn = sqlite3.connect(str(db_path))
    try:
        _ = conn.execute(
            "INSERT INTO task_runs (id, task_id, status, outcome, summary, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, task_id, "completed", "completed", summary, metadata),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_event(db_path: Path, *, event_id: int, task_id: str, run_id: int | None, kind: str) -> None:
    """Insert a task_events row.

    Args:
        db_path: Path to the sqlite database file.
        event_id: The event row id (replay cursor value).
        task_id: The owning task id.
        run_id: The closing run id, or None.
        kind: The event kind string.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        _ = conn.execute(
            "INSERT INTO task_events (id, task_id, run_id, kind, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, task_id, run_id, kind, None, 0),
        )
        conn.commit()
    finally:
        conn.close()


def test_read_recovers_summary_and_metadata_via_join(tmp_path: Path) -> None:
    """A completed event recovers the worker summary/metadata from the joined run row."""
    db = tmp_path / "kanban.db"
    _init_db(db)
    _insert_run(db, run_id=1, task_id="t1", summary="A done\nignored", metadata='{"gate": "pass", "x": 1}')
    _insert_event(db, event_id=2, task_id="t1", run_id=1, kind="completed")
    reader = SqliteTaskEventReader(connect=_factory(db))

    rows = reader.read_terminal_events(after_event_id=0, limit=100)

    assert len(rows) == 1
    row = rows[0]
    assert row["task_id"] == "t1"
    assert row["event_id"] == 2
    assert row["kind"] == "completed"
    assert row["summary"] == "A done\nignored"
    assert row["metadata"] == {"gate": "pass", "x": 1}


def test_read_filters_non_terminal_and_respects_cursor(tmp_path: Path) -> None:
    """Only terminal events with id > cursor are returned, ordered ascending."""
    db = tmp_path / "kanban.db"
    _init_db(db)
    _insert_event(db, event_id=1, task_id="t1", run_id=None, kind="created")
    _insert_event(db, event_id=2, task_id="t1", run_id=None, kind="completed")
    _insert_event(db, event_id=3, task_id="t1", run_id=None, kind="heartbeat")
    _insert_event(db, event_id=4, task_id="t2", run_id=None, kind="timed_out")
    reader = SqliteTaskEventReader(connect=_factory(db))

    all_terminal = reader.read_terminal_events(after_event_id=0, limit=100)
    assert [r["event_id"] for r in all_terminal] == [2, 4]

    after_cursor = reader.read_terminal_events(after_event_id=2, limit=100)
    assert [r["event_id"] for r in after_cursor] == [4]


def test_read_respects_limit_and_orders_by_event_id(tmp_path: Path) -> None:
    """The limit caps the batch and results are ordered ascending by event_id."""
    db = tmp_path / "kanban.db"
    _init_db(db)
    # Insert out of order to confirm ORDER BY.
    _insert_event(db, event_id=7, task_id="t1", run_id=None, kind="completed")
    _insert_event(db, event_id=5, task_id="t1", run_id=None, kind="completed")
    _insert_event(db, event_id=6, task_id="t1", run_id=None, kind="completed")
    reader = SqliteTaskEventReader(connect=_factory(db))

    rows = reader.read_terminal_events(after_event_id=0, limit=2)

    assert [r["event_id"] for r in rows] == [5, 6]


def test_read_null_run_yields_empty_summary_and_metadata(tmp_path: Path) -> None:
    """An event with no joined run row yields empty summary and empty metadata."""
    db = tmp_path / "kanban.db"
    _init_db(db)
    _insert_event(db, event_id=1, task_id="t1", run_id=None, kind="blocked")
    reader = SqliteTaskEventReader(connect=_factory(db))

    rows = reader.read_terminal_events(after_event_id=0, limit=100)

    assert len(rows) == 1
    assert rows[0]["summary"] == ""
    assert rows[0]["metadata"] == {}


@pytest.mark.parametrize("metadata", [None, "", "not-json", "[1, 2, 3]"])
def test_read_malformed_or_missing_metadata_yields_empty_dict(tmp_path: Path, metadata: str | None) -> None:
    """NULL, empty, non-JSON, and non-object metadata all decode to an empty dict."""
    db = tmp_path / "kanban.db"
    _init_db(db)
    _insert_run(db, run_id=1, task_id="t1", summary="done", metadata=metadata)
    _insert_event(db, event_id=1, task_id="t1", run_id=1, kind="completed")
    reader = SqliteTaskEventReader(connect=_factory(db))

    rows = reader.read_terminal_events(after_event_id=0, limit=100)

    assert rows[0]["metadata"] == {}
