"""KanbanBoard port: isolates all kanban tool/REST calls.

See: specs/001-attractor-kanban/contracts/ports.md §KanbanBoard
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping

    from hermes_attractor.domain.card import Card


class KanbanBoard(Protocol):  # pragma: no cover
    """Port isolating every kanban tool/REST call (research risk R2 lives here).

    Contract notes:
        ``create_card`` MUST pass ``card.idempotency_key.value`` so re-creation
        is a no-op returning the existing non-archived task id (research D5, FR-024).
        Implementations MUST NOT raise on a duplicate key — they return the existing id.
    """

    def create_card(self, card: Card) -> str:
        """Create (or deduplicate via idempotency_key) a kanban card.

        Args:
            card: The Card to dispatch.

        Returns:
            The task_id of the newly created or existing card.
        """
        ...

    def block_card(self, task_id: str, *, reason: str, body: str) -> None:
        """Block a card awaiting human action (human-in-the-loop pause).

        Args:
            task_id: The task identifier to block.
            reason: Short reason for the block (displayed to the human).
            body: Detailed instructions for human action.
        """
        ...

    def complete_card(self, task_id: str, *, summary: str, metadata: Mapping[str, object]) -> None:
        """Mark a card complete with a structured result (used by TOOL nodes).

        Args:
            task_id: The task identifier to complete.
            summary: Human-readable completion summary.
            metadata: Structured output data attached to the completion event.
        """
        ...
