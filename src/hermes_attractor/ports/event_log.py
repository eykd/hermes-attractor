"""EventLog port: tailing the durable kanban task_events log.

See: specs/001-attractor-kanban/contracts/ports.md §EventLog
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hermes_attractor.domain.card import CardResult


class EventLog(Protocol):  # pragma: no cover
    """Port for reading terminal kanban completion events (research D2/D6).

    Implementations tail the durable ``task_events`` log in batches.

    Contract notes:
        ``read_since`` returns ONLY terminal event kinds:
        ``completed | blocked | gave_up | crashed | timed_out``.
        Events are ordered ascending by ``event_id``.
    """

    def read_since(self, last_seen_event_id: int) -> Sequence[CardResult]:
        """Return terminal completion events with event_id > last_seen_event_id.

        Args:
            last_seen_event_id: The replay cursor; only events with a higher id
                are returned.

        Returns:
            Sequence of CardResult objects ordered ascending by event_id.
        """
        ...
