"""HermesKanbanBoard adapter: bridges the KanbanBoard port to Hermes tool calls.

All kanban field names are isolated here to contain the R2 (field-name drift)
risk identified in research. If the Hermes tool surface changes, only this
file needs updating.

See: specs/001-attractor-kanban/contracts/ports.md §KanbanBoard
See: specs/001-attractor-kanban/research.md §R2
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

    from hermes_attractor.domain.card import Card
    from hermes_attractor.ports.hermes_tool_client import HermesToolClient

_log = logging.getLogger(__name__)

#: Hermes tool name constants — single source of truth for R2 risk containment.
#: If the Hermes kanban tool surface renames a tool, update this file only.
_TOOL_CREATE_TASK = "create_task"
_TOOL_BLOCK_TASK = "block_task"
_TOOL_COMPLETE_TASK = "complete_task"

#: Response field name constants for ``create_task`` (R2 drift isolation).
_FIELD_TASK_ID = "task_id"

#: Gate-verdict trust policy (plan.md §Security §Gate-verdict trust):
#:   A missing or malformed ``gate`` field in the card result metadata is treated
#:   as a FAIL verdict, never as a PASS. See ``_gate_verdict_pass()`` in
#:   ``run_execution.py`` which enforces this fail-secure policy.


class HermesKanbanBoard:
    """KanbanBoard adapter that delegates to the Hermes tool surface.

    All kanban field names are defined as constants in this module to
    centralise R2 risk: if the Hermes API changes, only this file
    needs updating (plan.md §Security §Gate-verdict trust).

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

    def create_card(self, card: Card) -> str:
        """Create (or deduplicate) a kanban card via the Hermes ``create_task`` tool.

        Passes ``card.idempotency_key.value`` so re-creation is a no-op returning
        the existing task_id (research D5, FR-024). Never raises on duplicate keys.

        Args:
            card: The Card to dispatch.

        Returns:
            The task_id string for the new or existing card.
        """
        response = self._client.call(
            _TOOL_CREATE_TASK,
            idempotency_key=card.idempotency_key.value,
            assignee=card.assignee_profile,
            body=card.body,
            parent_task_ids=list(card.parent_task_ids),
            retry_limit=card.retry_limit,
            kind=card.kind.value,
        )
        result: dict[str, object] = cast("dict[str, object]", response) if isinstance(response, dict) else {}
        return str(result.get(_FIELD_TASK_ID, ""))

    def block_card(self, task_id: str, *, reason: str, body: str) -> None:
        """Block a card awaiting human action via the Hermes ``block_task`` tool.

        Args:
            task_id: The task identifier to block.
            reason: Short reason for the block.
            body: Detailed instructions for the human reviewer.
        """
        _ = self._client.call(
            _TOOL_BLOCK_TASK,
            task_id=task_id,
            reason=reason,
            body=body,
        )

    def complete_card(self, task_id: str, *, summary: str, metadata: Mapping[str, object]) -> None:
        """Mark a card complete via the Hermes ``complete_task`` tool.

        Args:
            task_id: The task identifier to complete.
            summary: Human-readable completion summary.
            metadata: Structured output attached to the completion event.
        """
        _ = self._client.call(
            _TOOL_COMPLETE_TASK,
            task_id=task_id,
            summary=summary,
            metadata=dict(metadata),
        )
