"""Unit tests for the EventLog port and Hermes event-log adapter (RED phase M3 US3).

Tests fail until ports/event_log.py and adapters/event_log.py are implemented.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hermes_attractor.adapters.event_log import EVENT_LOG_BATCH_SIZE, HermesEventLog
from hermes_attractor.domain.card import CardResult
from hermes_attractor.ports.event_log import EventLog

pytestmark = pytest.mark.unit

#: Terminal event kinds per the contract spec.
_TERMINAL_KINDS = {"completed", "blocked", "gave_up", "crashed", "timed_out"}
#: Non-terminal event kinds that should be filtered out.
_NON_TERMINAL_KINDS = {"started", "assigned", "updated", "commented"}


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
    """Build a raw Hermes event dict for testing.

    Args:
        task_id: The task identifier.
        event_id: The monotonic event sequence number.
        kind: The event kind string.

    Returns:
        A dict simulating a Hermes event payload.
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
    raw_events = [
        _make_event("task-001", 5, "completed"),
        _make_event("task-002", 7, "blocked"),
        _make_event("task-003", 9, "gave_up"),
    ]
    tool_client = MagicMock()
    tool_client.call.return_value = {"events": raw_events}
    log = HermesEventLog(tool_client=tool_client)

    results = log.read_since(last_seen_event_id=0)

    assert len(results) == 3
    assert all(isinstance(r, CardResult) for r in results)
    event_ids = [r.event_id for r in results]
    assert event_ids == sorted(event_ids), "Events must be ordered by event_id"


def test_read_since_filters_out_non_terminal_events() -> None:
    """HermesEventLog.read_since filters out non-terminal event kinds."""
    raw_events = [
        _make_event("task-001", 1, "started"),  # non-terminal
        _make_event("task-002", 2, "completed"),  # terminal
        _make_event("task-003", 3, "assigned"),  # non-terminal
        _make_event("task-004", 4, "timed_out"),  # terminal
    ]
    tool_client = MagicMock()
    tool_client.call.return_value = {"events": raw_events}
    log = HermesEventLog(tool_client=tool_client)

    results = log.read_since(last_seen_event_id=0)

    kinds = {r.event_kind for r in results}
    assert kinds.issubset(_TERMINAL_KINDS), f"Non-terminal events leaked: {kinds - _TERMINAL_KINDS}"
    assert len(results) == 2


def test_read_since_returns_only_events_after_cursor() -> None:
    """HermesEventLog.read_since only returns events with event_id > last_seen_event_id."""
    raw_events = [
        _make_event("task-001", 10, "completed"),
        _make_event("task-002", 15, "blocked"),
        _make_event("task-003", 20, "completed"),
    ]
    tool_client = MagicMock()
    tool_client.call.return_value = {"events": raw_events}
    log = HermesEventLog(tool_client=tool_client)

    # Request events after event_id=12; should get 15 and 20 only.
    results = log.read_since(last_seen_event_id=12)

    event_ids = {r.event_id for r in results}
    assert 10 not in event_ids, "Event at id=10 is <= cursor 12; should be excluded"
    assert 15 in event_ids
    assert 20 in event_ids


def test_read_since_passes_last_event_id_to_hermes_tool() -> None:
    """HermesEventLog.read_since passes last_seen_event_id to the Hermes tool call."""
    tool_client = MagicMock()
    tool_client.call.return_value = {"events": []}
    log = HermesEventLog(tool_client=tool_client)

    _ = log.read_since(last_seen_event_id=42)

    tool_client.call.assert_called_once()
    call_args = tool_client.call.call_args
    # The cursor should be passed to the tool call.
    assert 42 in call_args.args or any(v == 42 for v in call_args.kwargs.values())


def test_read_since_returns_empty_when_no_events() -> None:
    """HermesEventLog.read_since returns an empty sequence when no events exist."""
    tool_client = MagicMock()
    tool_client.call.return_value = {"events": []}
    log = HermesEventLog(tool_client=tool_client)

    results = log.read_since(last_seen_event_id=0)

    assert list(results) == []


def test_read_since_reads_in_batches_capped_at_batch_size() -> None:
    """HermesEventLog.read_since issues batched reads of at most EVENT_LOG_BATCH_SIZE events."""
    assert EVENT_LOG_BATCH_SIZE == 100, "EVENT_LOG_BATCH_SIZE must be 100 per spec"

    # Return exactly one batch worth of events.
    raw_events = [_make_event(f"task-{i:03d}", i + 1, "completed") for i in range(EVENT_LOG_BATCH_SIZE)]
    tool_client = MagicMock()
    tool_client.call.return_value = {"events": raw_events}
    log = HermesEventLog(tool_client=tool_client)

    results = log.read_since(last_seen_event_id=0)

    assert len(results) == EVENT_LOG_BATCH_SIZE
    # Verify the batch size limit is passed in the tool call.
    call_args = tool_client.call.call_args
    assert EVENT_LOG_BATCH_SIZE in call_args.args or any(v == EVENT_LOG_BATCH_SIZE for v in call_args.kwargs.values())


def test_read_since_handles_non_dict_response_gracefully() -> None:
    """HermesEventLog.read_since returns empty sequence when response is not a dict."""
    tool_client = MagicMock()
    tool_client.call.return_value = None  # non-dict response
    log = HermesEventLog(tool_client=tool_client)

    results = log.read_since(last_seen_event_id=0)

    assert list(results) == []


def test_read_since_handles_non_list_events_field_gracefully() -> None:
    """HermesEventLog.read_since returns empty sequence when 'events' is not a list."""
    tool_client = MagicMock()
    tool_client.call.return_value = {"events": "not-a-list"}
    log = HermesEventLog(tool_client=tool_client)

    results = log.read_since(last_seen_event_id=0)

    assert list(results) == []


def test_read_since_handles_non_dict_metadata_in_event() -> None:
    """HermesEventLog.read_since uses empty dict when event metadata is not a dict."""
    raw_event = {
        "task_id": "task-001",
        "event_id": 5,
        "kind": "completed",
        "summary": "Done.",
        "metadata": "not-a-dict",  # malformed metadata
    }
    tool_client = MagicMock()
    tool_client.call.return_value = {"events": [raw_event]}
    log = HermesEventLog(tool_client=tool_client)

    results = log.read_since(last_seen_event_id=0)

    assert len(results) == 1
    assert results[0].metadata == {}


def test_read_since_maps_event_fields_to_card_result() -> None:
    """HermesEventLog.read_since correctly maps raw event fields to CardResult."""
    raw_event = {
        "task_id": "task-xyz",
        "event_id": 99,
        "kind": "completed",
        "summary": "All done.",
        "metadata": {"score": 1.0},
    }
    tool_client = MagicMock()
    tool_client.call.return_value = {"events": [raw_event]}
    log = HermesEventLog(tool_client=tool_client)

    results = log.read_since(last_seen_event_id=0)

    assert len(results) == 1
    r = results[0]
    assert r.task_id == "task-xyz"
    assert r.event_id == 99
    assert r.event_kind == "completed"
    assert r.summary == "All done."
    assert r.metadata == {"score": 1.0}
