"""SqliteTaskEventReader: reads terminal kanban events from the ``task_events`` log.

Concrete :class:`~hermes_attractor.ports.task_event_reader.TaskEventReader` that queries
the kanban SQLite database, joining ``task_events`` to ``task_runs`` to recover the
worker's structured ``metadata`` and full ``summary`` (the event payload only carries a
truncated first-line summary). Verified against hermes-agent 0.15.2; see
``specs/001-attractor-kanban/research-hermes-kanban.md`` §Phase 1 (C).

The connection is obtained through an injected zero-argument factory so the production
wiring can hand in ``hermes_cli.kanban_db.connect`` while unit tests inject a plain stdlib
``sqlite3`` connection over a database that mirrors the kanban schema. No ``hermes_cli``
import lives in this module.

See: specs/001-attractor-kanban/contracts/ports.md §EventLog
"""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

__all__ = ["SqliteTaskEventReader"]

_log = logging.getLogger(__name__)

#: Terminal event kinds read by the reconciler (research §Phase 1 (C)).
_TERMINAL_KINDS: tuple[str, ...] = ("completed", "blocked", "gave_up", "crashed", "timed_out")

#: Join read: terminal events past the cursor, with the worker metadata/summary recovered
#: from the closing run row (``task_events.payload`` lacks the structured metadata).
_READ_SQL = f"""
SELECT e.id AS event_id, e.task_id AS task_id, e.kind AS kind,
       r.summary AS summary, r.metadata AS metadata
FROM task_events e
LEFT JOIN task_runs r ON e.run_id = r.id
WHERE e.id > ? AND e.kind IN ({",".join("?" for _ in _TERMINAL_KINDS)})
ORDER BY e.id ASC
LIMIT ?
"""  # noqa: S608  # fixed terminal-kind placeholders, not user input


class SqliteTaskEventReader:
    """TaskEventReader backed by the kanban ``task_events`` SQLite table.

    Attributes:
        _connect: Zero-argument factory returning an open kanban DB connection.
    """

    def __init__(self, connect: Callable[[], sqlite3.Connection]) -> None:
        """Initialise with a connection factory.

        Args:
            connect: Callable returning a fresh ``sqlite3.Connection`` to the kanban DB.
                Each ``read_terminal_events`` call opens and closes one connection.
        """
        super().__init__()
        self._connect = connect

    def read_terminal_events(self, *, after_event_id: int, limit: int) -> Sequence[Mapping[str, object]]:
        """Return terminal event rows with ``event_id > after_event_id`` (see port).

        Args:
            after_event_id: The replay cursor; only events with a higher id are returned.
            limit: Maximum number of terminal events to return in this batch.

        Returns:
            A list of normalized event-row mappings ordered ascending by ``event_id``;
            ``metadata`` is the parsed worker dict (``{}`` when absent or malformed).
        """
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        with contextlib.closing(conn):
            cursor = conn.execute(_READ_SQL, (after_event_id, *_TERMINAL_KINDS, limit))
            rows = cursor.fetchall()

        return [
            {
                "task_id": str(row["task_id"]),
                "event_id": int(row["event_id"]),
                "kind": str(row["kind"]),
                "summary": str(row["summary"]) if row["summary"] is not None else "",
                "metadata": _parse_metadata(row["metadata"]),
            }
            for row in rows
        ]


def _parse_metadata(raw: object) -> dict[str, object]:
    """Parse a ``task_runs.metadata`` JSON value into a dict, defaulting to ``{}``.

    Args:
        raw: The raw metadata column value (JSON text, ``None``, or unexpected type).

    Returns:
        The decoded metadata dict, or an empty dict when absent/malformed/non-object.
    """
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        decoded: object = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(decoded, dict):
        return cast("dict[str, object]", decoded)
    return {}
