"""Unit tests for Card, CardResult, and CardKind domain value objects (RED phase M2 US2).

Tests fail until src/hermes_attractor/domain/card.py is implemented.
"""

from __future__ import annotations

import pytest

from hermes_attractor.domain.card import Card, CardKind, CardResult
from hermes_attractor.domain.run import IdempotencyKey

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# CardKind enum
# ---------------------------------------------------------------------------


def test_card_kind_has_required_members() -> None:
    """CardKind must declare WORK, GATE, and HUMAN."""
    required = {"WORK", "GATE", "HUMAN"}
    actual = {m.name for m in CardKind}
    assert required.issubset(actual), f"Missing CardKind members: {required - actual}"


def test_card_kind_members_are_exactly_the_required_set() -> None:
    """CardKind must not have extra members beyond WORK, GATE, HUMAN."""
    expected = {"WORK", "GATE", "HUMAN"}
    actual = {m.name for m in CardKind}
    assert actual == expected, f"CardKind has unexpected members: {actual - expected}"


# ---------------------------------------------------------------------------
# Card value object
# ---------------------------------------------------------------------------


def test_card_has_required_fields() -> None:
    """Card must have idempotency_key, assignee_profile, body, parent_task_ids, retry_limit, kind."""
    key = IdempotencyKey.for_node("run1", "work", 1)
    card = Card(
        idempotency_key=key,
        assignee_profile="coder",
        body="Do the work.",
        parent_task_ids=[],
        retry_limit=3,
        kind=CardKind.WORK,
    )
    assert card.idempotency_key is key
    assert card.assignee_profile == "coder"
    assert card.body == "Do the work."
    assert list(card.parent_task_ids) == []
    assert card.retry_limit == 3
    assert card.kind is CardKind.WORK


def test_card_with_parent_task_ids() -> None:
    """Card accepts a non-empty parent_task_ids sequence."""
    key = IdempotencyKey.for_node("run1", "gate", 1)
    card = Card(
        idempotency_key=key,
        assignee_profile="reviewer",
        body="Review the work.",
        parent_task_ids=["task-001", "task-002"],
        retry_limit=1,
        kind=CardKind.GATE,
    )
    assert list(card.parent_task_ids) == ["task-001", "task-002"]
    assert card.kind is CardKind.GATE


def test_card_human_kind() -> None:
    """Card accepts HUMAN kind."""
    key = IdempotencyKey.for_node("run1", "human", 1)
    card = Card(
        idempotency_key=key,
        assignee_profile="human",
        body="Please review.",
        parent_task_ids=[],
        retry_limit=0,
        kind=CardKind.HUMAN,
    )
    assert card.kind is CardKind.HUMAN


# ---------------------------------------------------------------------------
# CardResult value object
# ---------------------------------------------------------------------------


def test_card_result_has_required_fields() -> None:
    """CardResult must have task_id, event_id, event_kind, summary, metadata."""
    result = CardResult(
        task_id="task-xyz",
        event_id=42,
        event_kind="completed",
        summary="Work done.",
        metadata={},
    )
    assert result.task_id == "task-xyz"
    assert result.event_id == 42
    assert result.event_kind == "completed"
    assert result.summary == "Work done."
    assert result.metadata == {}


def test_card_result_with_metadata() -> None:
    """CardResult accepts non-empty metadata."""
    result = CardResult(
        task_id="t1",
        event_id=1,
        event_kind="blocked",
        summary="Needs review.",
        metadata={"reason": "failed gate", "score": 0.4},
    )
    assert result.metadata["reason"] == "failed gate"
    assert result.metadata["score"] == 0.4
