"""Unit tests for the EventLog port and Hermes event-log adapter.

``HermesEventLog`` maps terminal ``task_events`` rows (supplied by a TaskEventReader)
to domain ``CardResult`` objects. These tests inject a fake reader.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hermes_attractor.adapters.event_log import HermesEventLog
from hermes_attractor.domain.card import CardResult
from hermes_attractor.domain.constants import EVENT_LOG_BATCH_SIZE
from hermes_attractor.ports.event_log import EventLog

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

pytestmark = pytest.mark.unit

#: Terminal event kinds per the contract spec.
_TERMINAL_KINDS = {"completed", "blocked", "gave_up", "crashed", "timed_out"}


class _FakeReader:
    """A fake TaskEventReader that returns preset rows and records its call args."""

    def __init__(self, events: Sequence[Mapping[str, object]]) -> None:
        """Initialise with the event rows to return.

        Args:
            events: The rows ``read_terminal_events`` should return.
        """
        super().__init__()
        self._events = events
        self.calls: list[dict[str, int]] = []

    def read_terminal_events(self, *, after_event_id: int, limit: int) -> Sequence[Mapping[str, object]]:
        """Record the call args and return the preset rows.

        Args:
            after_event_id: The replay cursor passed by the adapter.
            limit: The batch-size limit passed by the adapter.

        Returns:
            The preset event rows.
        """
        self.calls.append({"after_event_id": after_event_id, "limit": limit})
        return self._events


# ---------------------------------------------------------------------------
# Protocol surface
# ---------------------------------------------------------------------------


def test_event_log_protocol_has_read_since() -> None:
    """EventLog Protocol must declare read_since method."""
    assert hasattr(EventLog, "read_since")
    assert callable(EventLog.read_since)


# ---------------------------------------------------------------------------
# HermesEventLog adapter
# ---------------------------------------------------------------------------


def _make_event(task_id: str, event_id: int, kind: str) -> dict[str, object]:
    """Build a normalized event-row dict for testing.

    Args:
        task_id: The task identifier.
        event_id: The monotonic event sequence number.
        kind: The event kind string.

    Returns:
        A dict matching the TaskEventReader row contract.
    """
    return {
        "task_id": task_id,
        "event_id": event_id,
        "kind": kind,
        "summary": f"Event {event_id} for {task_id}",
        "metadata": {},
    }


def test_read_since_returns_terminal_events_ordered_by_event_id() -> None:
    """HermesEventLog.read_since returns terminal CardResults ordered by event_id."""
    reader = _FakeReader(
        [
            _make_event("task-003", 9, "gave_up"),
            _make_event("task-001", 5, "completed"),
            _make_event("task-002", 7, "blocked"),
        ]
    )
    log = HermesEventLog(reader=reader)

    results = log.read_since(last_seen_event_id=0)

    assert len(results) == 3
    assert all(isinstance(r, CardResult) for r in results)
    event_ids = [r.event_id for r in results]
    assert event_ids == sorted(event_ids), "Events must be ordered by event_id"


def test_read_since_filters_out_non_terminal_events() -> None:
    """HermesEventLog.read_since filters out non-terminal event kinds defensively."""
    reader = _FakeReader(
        [
            _make_event("task-001", 1, "started"),  # non-terminal
            _make_event("task-002", 2, "completed"),  # terminal
            _make_event("task-003", 3, "assigned"),  # non-terminal
            _make_event("task-004", 4, "timed_out"),  # terminal
        ]
    )
    log = HermesEventLog(reader=reader)

    results = log.read_since(last_seen_event_id=0)

    kinds = {r.event_kind for r in results}
    assert kinds.issubset(_TERMINAL_KINDS), f"Non-terminal events leaked: {kinds - _TERMINAL_KINDS}"
    assert len(results) == 2


def test_read_since_returns_only_events_after_cursor() -> None:
    """HermesEventLog.read_since only returns events with event_id > last_seen_event_id."""
    reader = _FakeReader(
        [
            _make_event("task-001", 10, "completed"),
            _make_event("task-002", 15, "blocked"),
            _make_event("task-003", 20, "completed"),
        ]
    )
    log = HermesEventLog(reader=reader)

    # Request events after event_id=12; should get 15 and 20 only.
    results = log.read_since(last_seen_event_id=12)

    event_ids = {r.event_id for r in results}
    assert 10 not in event_ids, "Event at id=10 is <= cursor 12; should be excluded"
    assert 15 in event_ids
    assert 20 in event_ids


def test_read_since_passes_cursor_and_batch_size_to_reader() -> None:
    """HermesEventLog.read_since passes the cursor and batch-size limit to the reader."""
    reader = _FakeReader([])
    log = HermesEventLog(reader=reader)

    _ = log.read_since(last_seen_event_id=42)

    assert reader.calls == [{"after_event_id": 42, "limit": EVENT_LOG_BATCH_SIZE}]


def test_read_since_returns_empty_when_no_events() -> None:
    """HermesEventLog.read_since returns an empty sequence when no events exist."""
    reader = _FakeReader([])
    log = HermesEventLog(reader=reader)

    results = log.read_since(last_seen_event_id=0)

    assert list(results) == []


def test_read_since_reads_in_batches_capped_at_batch_size() -> None:
    """HermesEventLog.read_since requests at most EVENT_LOG_BATCH_SIZE events per call."""
    assert EVENT_LOG_BATCH_SIZE == 100, "EVENT_LOG_BATCH_SIZE must be 100 per spec"

    raw_events = [_make_event(f"task-{i:03d}", i + 1, "completed") for i in range(EVENT_LOG_BATCH_SIZE)]
    reader = _FakeReader(raw_events)
    log = HermesEventLog(reader=reader)

    results = log.read_since(last_seen_event_id=0)

    assert len(results) == EVENT_LOG_BATCH_SIZE
    assert reader.calls[0]["limit"] == EVENT_LOG_BATCH_SIZE


def test_read_since_handles_non_dict_metadata_in_event() -> None:
    """HermesEventLog.read_since uses empty dict when an event's metadata is not a dict."""
    reader = _FakeReader(
        [
            {
                "task_id": "task-001",
                "event_id": 5,
                "kind": "completed",
                "summary": "Done.",
                "metadata": "not-a-dict",  # malformed metadata
            }
        ]
    )
    log = HermesEventLog(reader=reader)

    results = log.read_since(last_seen_event_id=0)

    assert len(results) == 1
    assert results[0].metadata == {}


def test_read_since_maps_event_fields_to_card_result() -> None:
    """HermesEventLog.read_since correctly maps raw event fields to CardResult."""
    reader = _FakeReader(
        [
            {
                "task_id": "task-xyz",
                "event_id": 99,
                "kind": "completed",
                "summary": "All done.",
                "metadata": {"score": 1.0},
            }
        ]
    )
    log = HermesEventLog(reader=reader)

    results = log.read_since(last_seen_event_id=0)

    assert len(results) == 1
    r = results[0]
    assert r.task_id == "task-xyz"
    assert r.event_id == 99
    assert r.event_kind == "completed"
    assert r.summary == "All done."
    assert r.metadata == {"score": 1.0}
