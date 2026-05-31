"""HermesEventLog adapter: maps terminal ``task_events`` rows to domain CardResults.

Reads terminal completion events from a :class:`TaskEventReader` (which tails the durable
kanban ``task_events`` log) in batches of ``EVENT_LOG_BATCH_SIZE`` to bound memory and
replay duration (plan.md §Performance §Batch-boundary correctness).

Note on batch size: ``EVENT_LOG_BATCH_SIZE`` is a **throughput knob only**. The
reconciler's correctness does not depend on it — every event at or below the final
cursor is guaranteed to be processed regardless of how many batches it takes.
Fan-in aggregation state is stored as durable ``RunNode`` records (not derived by
re-reading events), so partial batches never leave the state machine in an
inconsistent position.

Verified against hermes-agent 0.15.2: there is no event-read *tool*; events are read from
the kanban DB via the :class:`TaskEventReader` port. See
``specs/001-attractor-kanban/research-hermes-kanban.md`` §Phase 1 (C).

See: specs/001-attractor-kanban/contracts/ports.md §EventLog
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from hermes_attractor.domain.card import CardResult
from hermes_attractor.domain.constants import EVENT_LOG_BATCH_SIZE

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hermes_attractor.ports.task_event_reader import TaskEventReader

__all__ = ["HermesEventLog"]

_log = logging.getLogger(__name__)

#: Terminal event kinds; all other kinds are filtered out (contracts/ports.md §EventLog).
_TERMINAL_KINDS: frozenset[str] = frozenset({"completed", "blocked", "gave_up", "crashed", "timed_out"})

#: Event-row field name constants (R2 risk containment).
_FIELD_TASK_ID = "task_id"
_FIELD_EVENT_ID = "event_id"
_FIELD_KIND = "kind"
_FIELD_SUMMARY = "summary"
_FIELD_METADATA = "metadata"


class HermesEventLog:
    """EventLog adapter backed by a :class:`TaskEventReader`.

    Reads terminal completion events in batches of ``EVENT_LOG_BATCH_SIZE`` events
    per call and maps each raw row to a :class:`CardResult`. Non-terminal events and
    events at or below the cursor are filtered out defensively.

    Attributes:
        _reader: The task-event reader.
    """

    def __init__(self, reader: TaskEventReader) -> None:
        """Initialise with a task-event reader.

        Args:
            reader: An object with a ``read_terminal_events(*, after_event_id, limit)`` method.
        """
        super().__init__()
        self._reader = reader

    def read_since(self, last_seen_event_id: int) -> Sequence[CardResult]:
        """Return terminal completion events with event_id > last_seen_event_id.

        Issues a single batched read of up to ``EVENT_LOG_BATCH_SIZE`` events.
        Filters to terminal event kinds only and orders results ascending by event_id.

        Args:
            last_seen_event_id: The replay cursor; only events with a higher id are
                returned.

        Returns:
            A sequence of CardResult objects for terminal events, ordered by event_id.
        """
        rows = self._reader.read_terminal_events(after_event_id=last_seen_event_id, limit=EVENT_LOG_BATCH_SIZE)

        results: list[CardResult] = []
        for event in rows:
            kind = str(event.get(_FIELD_KIND, ""))
            if kind not in _TERMINAL_KINDS:
                continue
            event_id = int(str(event.get(_FIELD_EVENT_ID, 0)))
            if event_id <= last_seen_event_id:
                continue
            task_id = str(event.get(_FIELD_TASK_ID, ""))
            summary = str(event.get(_FIELD_SUMMARY, ""))
            raw_metadata = event.get(_FIELD_METADATA, {})
            if isinstance(raw_metadata, dict):
                metadata: dict[str, object] = cast("dict[str, object]", raw_metadata)
            else:
                metadata = {}
            results.append(
                CardResult(
                    task_id=task_id,
                    event_id=event_id,
                    event_kind=kind,
                    summary=summary,
                    metadata=metadata,
                )
            )

        return sorted(results, key=lambda r: r.event_id)
