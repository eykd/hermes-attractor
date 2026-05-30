"""HermesEventLog adapter: reads terminal events from the Hermes task_events log.

Batches reads in groups of ``EVENT_LOG_BATCH_SIZE`` (from domain constants) to bound
memory and replay duration (plan.md §Performance §Batch-boundary correctness).

Note on batch size: ``EVENT_LOG_BATCH_SIZE`` is a **throughput knob only**. The
reconciler's correctness does not depend on it — every event at or below the final
cursor is guaranteed to be processed regardless of how many batches it takes.
Fan-in aggregation state is stored as durable ``RunNode`` records (not derived by
re-reading events), so partial batches never leave the state machine in an
inconsistent position.

See: specs/001-attractor-kanban/contracts/ports.md §EventLog
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from hermes_attractor.domain.card import CardResult
from hermes_attractor.domain.constants import EVENT_LOG_BATCH_SIZE

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hermes_attractor.ports.hermes_tool_client import HermesToolClient

__all__ = ["HermesEventLog"]

_log = logging.getLogger(__name__)

#: Terminal event kinds; all other kinds are filtered out (contracts/ports.md §EventLog).
_TERMINAL_KINDS: frozenset[str] = frozenset({"completed", "blocked", "gave_up", "crashed", "timed_out"})

#: Hermes tool name for reading task events.
_TOOL_READ_TASK_EVENTS = "read_task_events"

#: Response field names (R2 risk containment).
_FIELD_EVENTS = "events"
_FIELD_TASK_ID = "task_id"
_FIELD_EVENT_ID = "event_id"
_FIELD_KIND = "kind"
_FIELD_SUMMARY = "summary"
_FIELD_METADATA = "metadata"


class HermesEventLog:
    """EventLog adapter backed by the Hermes ``read_task_events`` tool.

    Reads terminal completion events in batches of ``EVENT_LOG_BATCH_SIZE``
    events per call. Non-terminal events are filtered out client-side.

    Attributes:
        _client: The Hermes tool client.
    """

    def __init__(self, tool_client: HermesToolClient) -> None:
        """Initialise with a Hermes tool client.

        Args:
            tool_client: An object with a ``call(tool_name, **kwargs)`` method.
        """
        super().__init__()
        self._client = tool_client

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
        response = self._client.call(
            _TOOL_READ_TASK_EVENTS,
            after_event_id=last_seen_event_id,
            limit=EVENT_LOG_BATCH_SIZE,
        )
        raw: dict[str, object] = cast("dict[str, object]", response) if isinstance(response, dict) else {}
        raw_events = raw.get(_FIELD_EVENTS, [])
        if isinstance(raw_events, list):
            events_list: list[dict[str, object]] = cast("list[dict[str, object]]", raw_events)
        else:
            events_list = []

        results: list[CardResult] = []
        for event in events_list:
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
