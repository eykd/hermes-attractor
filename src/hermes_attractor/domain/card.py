"""Card and CardResult domain value objects (DTOs crossing the KanbanBoard port).

These are pure domain records. Zero external dependencies.

See: specs/001-attractor-kanban/data-model.md §DTOs crossing the kanban port
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from hermes_attractor.domain.run import IdempotencyKey


class CardKind(enum.Enum):
    """The kind of kanban card being dispatched.

    Attributes:
        WORK: A standard codergen/agent work card.
        GATE: A goal-gate review card.
        HUMAN: A durable pause waiting for human input.
    """

    WORK = "WORK"
    GATE = "GATE"
    HUMAN = "HUMAN"


@dataclass(frozen=True)
class Card:
    """Input to ``KanbanBoard.create_card`` — a request to dispatch work to a profile.

    Attributes:
        idempotency_key: Unique key used for create deduplication (research D5, FR-024).
        assignee_profile: Hermes profile name to assign the card to.
        body: Task body / prompt text.
        parent_task_ids: Ordered list of task ids whose completion this card depends on.
        retry_limit: Maximum number of retries before treating the card as failed.
        kind: The kind of work this card represents.
    """

    idempotency_key: IdempotencyKey
    assignee_profile: str
    body: str
    parent_task_ids: Sequence[str]
    retry_limit: int
    kind: CardKind


@dataclass(frozen=True)
class CardResult:
    """Result returned by the ``EventLog`` or ``KanbanBoard`` when a card completes.

    Attributes:
        task_id: The kanban task identifier.
        event_id: Monotonically increasing event log id (used as the replay cursor).
        event_kind: Terminal kanban event kind:
            ``completed | blocked | gave_up | crashed | timed_out``.
        summary: Human-readable completion summary.
        metadata: Structured output data (e.g. gate verdict JSON).
    """

    task_id: str
    event_id: int
    event_kind: str
    summary: str
    metadata: Mapping[str, object]
