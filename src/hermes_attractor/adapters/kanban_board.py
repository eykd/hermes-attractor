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
#: Verified against hermes-agent 0.15.2 (``tools/kanban_tools.py``). If the kanban tool
#: surface renames a tool, update this file only.
_TOOL_CREATE_TASK = "kanban_create"
_TOOL_BLOCK_TASK = "kanban_block"
_TOOL_COMPLETE_TASK = "kanban_complete"

#: Response field name constants for ``kanban_create`` (R2 drift isolation).
_FIELD_TASK_ID = "task_id"

#: Maximum length of a synthesized card title (``kanban_create`` requires ``title``).
_TITLE_MAX_LEN = 80

#: Gate-verdict trust policy (plan.md §Security §Gate-verdict trust):
#:   A missing or malformed ``gate`` field in the card result metadata is treated
#:   as a FAIL verdict, never as a PASS. See ``_gate_verdict_pass()`` in
#:   ``run_execution.py`` which enforces this fail-secure policy.


def _derive_title(card: Card) -> str:
    """Synthesize a ``kanban_create`` title from a card (the tool requires one).

    Uses the first non-empty line of the card body (capped at ``_TITLE_MAX_LEN``);
    falls back to the deterministic idempotency-key value when the body is blank.

    Args:
        card: The Card whose title to derive.

    Returns:
        A non-empty title string.
    """
    body = card.body.strip()
    if body:
        return body.splitlines()[0].strip()[:_TITLE_MAX_LEN]
    return card.idempotency_key.value


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
        """Create (or deduplicate) a kanban card via the Hermes ``kanban_create`` tool.

        Passes ``card.idempotency_key.value`` so re-creation is a no-op returning
        the existing task_id (research D5, FR-024). Never raises on duplicate keys.
        ``kanban_create`` requires a ``title`` and an ``assignee``; the title is
        synthesized from the card body (``_derive_title``). The card body maps to the
        tool ``body`` and parent task ids map to ``parents`` (verified API, 0.15.2);
        the domain ``retry_limit`` / ``kind`` have no ``kanban_create`` parameter.

        Args:
            card: The Card to dispatch.

        Returns:
            The task_id string for the new or existing card.
        """
        response = self._client.call(
            _TOOL_CREATE_TASK,
            title=_derive_title(card),
            assignee=card.assignee_profile,
            body=card.body,
            parents=list(card.parent_task_ids),
            idempotency_key=card.idempotency_key.value,
        )
        result: dict[str, object] = cast("dict[str, object]", response) if isinstance(response, dict) else {}
        return str(result.get(_FIELD_TASK_ID, ""))

    def block_card(self, task_id: str, *, reason: str, body: str) -> None:
        """Block a card awaiting human action via the Hermes ``kanban_block`` tool.

        ``kanban_block`` accepts only ``task_id`` and ``reason`` (no body field), so the
        detailed reviewer instructions in ``body`` are folded into the reason string.

        Args:
            task_id: The task identifier to block.
            reason: Short reason for the block.
            body: Detailed instructions for the human reviewer.
        """
        full_reason = f"{reason}\n\n{body}" if body else reason
        _ = self._client.call(
            _TOOL_BLOCK_TASK,
            task_id=task_id,
            reason=full_reason,
        )

    def complete_card(self, task_id: str, *, summary: str, metadata: Mapping[str, object]) -> None:
        """Mark a card complete via the Hermes ``kanban_complete`` tool.

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
