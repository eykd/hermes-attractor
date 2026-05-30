"""Unit tests for KanbanBoard port and HermesKanbanBoard adapter (RED phase M2 US2).

Tests fail until ports/kanban.py and adapters/kanban_board.py are implemented.
"""

from __future__ import annotations

import pytest

from hermes_attractor.adapters.kanban_board import HermesKanbanBoard
from hermes_attractor.domain.card import Card, CardKind
from hermes_attractor.domain.run import IdempotencyKey
from hermes_attractor.ports.kanban import KanbanBoard

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# KanbanBoard Protocol surface
# ---------------------------------------------------------------------------


def test_kanban_board_protocol_has_required_methods() -> None:
    """KanbanBoard Protocol must declare create_card, block_card, complete_card."""
    for method in ("create_card", "block_card", "complete_card"):
        assert hasattr(KanbanBoard, method), f"KanbanBoard missing method: {method}"
        assert callable(getattr(KanbanBoard, method))


# ---------------------------------------------------------------------------
# HermesKanbanBoard adapter
# ---------------------------------------------------------------------------


class _FakeHermesTool:
    """A fake Hermes tool client that records calls and returns preset responses."""

    def __init__(self) -> None:
        """Initialise with empty call log and default responses."""
        super().__init__()
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._responses: dict[str, object] = {}

    def set_response(self, tool_name: str, response: object) -> None:
        """Set the response for a given tool name.

        Args:
            tool_name: The Hermes tool name.
            response: The response to return.
        """
        self._responses[tool_name] = response

    def call(self, tool_name: str, **kwargs: object) -> object:
        """Record the call and return the preset response.

        Args:
            tool_name: The Hermes tool name.
            **kwargs: Tool arguments.

        Returns:
            Preset response for the tool, or None.
        """
        self.calls.append((tool_name, dict(kwargs)))
        return self._responses.get(tool_name)


def _make_card(node_id: str = "work", profile: str = "coder") -> Card:
    """Build a minimal Card for testing.

    Args:
        node_id: The node identifier for the idempotency key.
        profile: The assignee profile string.

    Returns:
        A Card instance.
    """
    return Card(
        idempotency_key=IdempotencyKey.for_node("run1", node_id, 1),
        assignee_profile=profile,
        body="Implement the feature.",
        parent_task_ids=[],
        retry_limit=2,
        kind=CardKind.WORK,
    )


def test_create_card_calls_hermes_with_idempotency_key() -> None:
    """HermesKanbanBoard.create_card passes the idempotency_key.value to Hermes."""
    fake_tool = _FakeHermesTool()
    fake_tool.set_response("create_task", {"task_id": "task-001"})
    board = HermesKanbanBoard(tool_client=fake_tool)
    card = _make_card()

    task_id = board.create_card(card)

    assert task_id == "task-001"
    assert len(fake_tool.calls) == 1
    call_name, call_kwargs = fake_tool.calls[0]
    assert call_name == "create_task"
    assert call_kwargs.get("idempotency_key") == card.idempotency_key.value


def test_create_card_returns_existing_task_id_on_duplicate_key() -> None:
    """HermesKanbanBoard.create_card returns existing task_id without raising on duplicate."""
    fake_tool = _FakeHermesTool()
    fake_tool.set_response("create_task", {"task_id": "task-existing", "duplicate": True})
    board = HermesKanbanBoard(tool_client=fake_tool)
    card = _make_card()

    # Should not raise even when response indicates a duplicate
    task_id = board.create_card(card)
    assert task_id == "task-existing"


def test_create_card_passes_assignee_profile_to_hermes() -> None:
    """HermesKanbanBoard.create_card passes the assignee profile to the Hermes tool."""
    fake_tool = _FakeHermesTool()
    fake_tool.set_response("create_task", {"task_id": "task-002"})
    board = HermesKanbanBoard(tool_client=fake_tool)
    card = _make_card(profile="reviewer")

    _ = board.create_card(card)

    _, call_kwargs = fake_tool.calls[0]
    assert call_kwargs.get("assignee") == "reviewer"


def test_block_card_calls_hermes_with_task_id_and_reason() -> None:
    """HermesKanbanBoard.block_card calls the correct Hermes tool with task_id and reason."""
    fake_tool = _FakeHermesTool()
    fake_tool.set_response("block_task", None)
    board = HermesKanbanBoard(tool_client=fake_tool)

    board.block_card("task-001", reason="Needs human review", body="Please check the output.")

    assert len(fake_tool.calls) == 1
    call_name, call_kwargs = fake_tool.calls[0]
    assert call_name == "block_task"
    assert call_kwargs.get("task_id") == "task-001"
    assert call_kwargs.get("reason") == "Needs human review"


def test_complete_card_calls_hermes_with_task_id_and_summary() -> None:
    """HermesKanbanBoard.complete_card calls the correct Hermes tool with task_id and summary."""
    fake_tool = _FakeHermesTool()
    fake_tool.set_response("complete_task", None)
    board = HermesKanbanBoard(tool_client=fake_tool)

    board.complete_card("task-001", summary="Done.", metadata={"score": 1.0})

    assert len(fake_tool.calls) == 1
    call_name, call_kwargs = fake_tool.calls[0]
    assert call_name == "complete_task"
    assert call_kwargs.get("task_id") == "task-001"
    assert call_kwargs.get("summary") == "Done."
