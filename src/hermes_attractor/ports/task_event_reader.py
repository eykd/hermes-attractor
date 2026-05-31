"""TaskEventReader port: low-level access to the durable kanban ``task_events`` log.

Verified against ``hermes-agent==0.15.2``: there is **no** event-read *tool*; terminal
completion events must be read from the kanban SQLite DB directly, joining
``task_events`` to ``task_runs`` to recover the worker's structured ``metadata`` and full
``summary`` (the event payload only carries a truncated summary).  See
``specs/001-attractor-kanban/research-hermes-kanban.md`` §Phase 1 (C).

This port isolates that DB read behind an injectable seam so :class:`HermesEventLog`
(which maps raw rows to :class:`CardResult`) stays fully unit-testable with a fake reader,
and the concrete :class:`SqliteTaskEventReader` can be exercised with a plain stdlib
sqlite database that mirrors the kanban schema.

See: specs/001-attractor-kanban/contracts/ports.md §EventLog
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class TaskEventReader(Protocol):  # pragma: no cover
    """Reads terminal kanban events from the durable ``task_events`` log.

    Contract notes:
        ``read_terminal_events`` returns ONLY terminal event kinds
        (``completed | blocked | gave_up | crashed | timed_out``), ordered ascending by
        ``event_id``, with ``event_id > after_event_id``, capped at ``limit`` rows.
        Each row is a mapping with keys ``task_id`` (str), ``event_id`` (int),
        ``kind`` (str), ``summary`` (str), and ``metadata`` (a dict — the worker's
        structured completion metadata, ``{}`` when absent).
    """

    def read_terminal_events(self, *, after_event_id: int, limit: int) -> Sequence[Mapping[str, object]]:
        """Return terminal event rows with ``event_id > after_event_id``.

        Args:
            after_event_id: The replay cursor; only events with a higher id are returned.
            limit: Maximum number of terminal events to return in this batch.

        Returns:
            A sequence of event-row mappings ordered ascending by ``event_id``.
        """
        ...
