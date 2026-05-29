"""Unit tests for the Run domain state machine: RunStatus, NodeRunStatus, Run, RunNode, IdempotencyKey.

These tests constitute the RED phase for M2 (US2: launch and execute a linear pipeline
with per-node profiles). They fail until src/hermes_attractor/domain/run.py is
implemented.
"""

from __future__ import annotations

import datetime

import pytest

from hermes_attractor.domain.pipeline import Context, GoalGatePolicy
from hermes_attractor.domain.run import (
    IdempotencyKey,
    NodeRunStatus,
    Run,
    RunNode,
    RunStatus,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# RunStatus enum
# ---------------------------------------------------------------------------


def test_run_status_has_all_required_members() -> None:
    """RunStatus must declare PENDING, RUNNING, PAUSED_HUMAN, BLOCKED, SUCCEEDED, FAILED."""
    required = {"PENDING", "RUNNING", "PAUSED_HUMAN", "BLOCKED", "SUCCEEDED", "FAILED"}
    actual = {member.name for member in RunStatus}
    assert required.issubset(actual), f"Missing RunStatus members: {required - actual}"


def test_run_status_members_are_exactly_the_required_set() -> None:
    """RunStatus must not contain any extra members beyond the spec."""
    expected = {"PENDING", "RUNNING", "PAUSED_HUMAN", "BLOCKED", "SUCCEEDED", "FAILED"}
    actual = {member.name for member in RunStatus}
    assert actual == expected, f"RunStatus has unexpected members: {actual - expected}"


# ---------------------------------------------------------------------------
# NodeRunStatus enum
# ---------------------------------------------------------------------------


def test_node_run_status_has_all_required_members() -> None:
    """NodeRunStatus must declare PENDING, DISPATCHED, RUNNING, SUCCEEDED, PARTIAL, FAILED, BLOCKED."""
    required = {"PENDING", "DISPATCHED", "RUNNING", "SUCCEEDED", "PARTIAL", "FAILED", "BLOCKED"}
    actual = {member.name for member in NodeRunStatus}
    assert required.issubset(actual), f"Missing NodeRunStatus members: {required - actual}"


def test_node_run_status_members_are_exactly_the_required_set() -> None:
    """NodeRunStatus must not contain any extra members beyond the spec."""
    expected = {"PENDING", "DISPATCHED", "RUNNING", "SUCCEEDED", "PARTIAL", "FAILED", "BLOCKED"}
    actual = {member.name for member in NodeRunStatus}
    assert actual == expected, f"NodeRunStatus has unexpected members: {actual - expected}"


# ---------------------------------------------------------------------------
# IdempotencyKey value object
# ---------------------------------------------------------------------------


def test_idempotency_key_for_node_basic_format() -> None:
    """IdempotencyKey.for_node produces 'attractor:<run_id>:<node_id>:attempt:<n>'."""
    key = IdempotencyKey.for_node("run1", "plan", 1)
    assert key.value == "attractor:run1:plan:attempt:1"


def test_idempotency_key_for_node_attempt_number_in_value() -> None:
    """IdempotencyKey.for_node encodes the attempt number correctly."""
    key = IdempotencyKey.for_node("run42", "codergen-a", 3)
    assert key.value == "attractor:run42:codergen-a:attempt:3"


def test_idempotency_key_for_node_raises_on_colon_in_node_id() -> None:
    """IdempotencyKey.for_node raises ValueError when node_id contains a colon."""
    with pytest.raises(ValueError, match="node_id"):
        _ = IdempotencyKey.for_node("run1", "bad:node", 1)


def test_idempotency_key_for_node_raises_on_colon_in_run_id() -> None:
    """IdempotencyKey.for_node raises ValueError when run_id contains a colon."""
    with pytest.raises(ValueError, match="run_id"):
        _ = IdempotencyKey.for_node("bad:run", "plan", 1)


def test_idempotency_key_value_is_string() -> None:
    """IdempotencyKey.value is a plain string."""
    key = IdempotencyKey.for_node("r", "n", 2)
    assert isinstance(key.value, str)


# ---------------------------------------------------------------------------
# Run entity
# ---------------------------------------------------------------------------


def test_run_has_required_fields() -> None:
    """Run must have run_id, spec_id, status, root_task_id, last_seen_event_id, context, created_at, updated_at."""
    now = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    ctx = Context(data={})
    run = Run(
        run_id="r1",
        spec_id="pipeline-spec",
        status=RunStatus.PENDING,
        root_task_id=None,
        last_seen_event_id=0,
        context=ctx,
        created_at=now,
        updated_at=now,
    )
    assert run.run_id == "r1"
    assert run.spec_id == "pipeline-spec"
    assert run.status is RunStatus.PENDING
    assert run.root_task_id is None
    assert run.last_seen_event_id == 0
    assert run.context is ctx
    assert run.created_at == now
    assert run.updated_at == now


def test_run_with_root_task_id() -> None:
    """Run accepts a non-None root_task_id."""
    now = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    run = Run(
        run_id="r2",
        spec_id="pipeline-spec",
        status=RunStatus.RUNNING,
        root_task_id="task-abc",
        last_seen_event_id=5,
        context=Context(data={}),
        created_at=now,
        updated_at=now,
    )
    assert run.root_task_id == "task-abc"
    assert run.last_seen_event_id == 5


# ---------------------------------------------------------------------------
# RunNode entity
# ---------------------------------------------------------------------------


def test_run_node_has_required_fields() -> None:
    """RunNode must have run_id, node_id, task_id, status, attempt, parent_node_ids, goal_gate_policy, output_ref."""
    run_node = RunNode(
        run_id="r1",
        node_id="work",
        task_id=None,
        status=NodeRunStatus.PENDING,
        attempt=1,
        parent_node_ids=[],
        goal_gate_policy=None,
        output_ref=None,
    )
    assert run_node.run_id == "r1"
    assert run_node.node_id == "work"
    assert run_node.task_id is None
    assert run_node.status is NodeRunStatus.PENDING
    assert run_node.attempt == 1
    assert run_node.parent_node_ids == []
    assert run_node.goal_gate_policy is None
    assert run_node.output_ref is None


def test_run_node_with_optional_fields() -> None:
    """RunNode accepts task_id, goal_gate_policy, output_ref, and parent_node_ids."""
    policy = GoalGatePolicy(retry_target="start", max_attempts=2)
    run_node = RunNode(
        run_id="r1",
        node_id="gate",
        task_id="task-xyz",
        status=NodeRunStatus.RUNNING,
        attempt=2,
        parent_node_ids=["work-a", "work-b"],
        goal_gate_policy=policy,
        output_ref="ref://output/r1/gate/2",
    )
    assert run_node.task_id == "task-xyz"
    assert run_node.attempt == 2
    assert run_node.parent_node_ids == ["work-a", "work-b"]
    assert run_node.goal_gate_policy is policy
    assert run_node.output_ref == "ref://output/r1/gate/2"


def test_run_node_attempt_must_be_at_least_one() -> None:
    """RunNode must reject attempt < 1."""
    with pytest.raises((ValueError, Exception)):
        _ = RunNode(
            run_id="r1",
            node_id="work",
            task_id=None,
            status=NodeRunStatus.PENDING,
            attempt=0,
            parent_node_ids=[],
            goal_gate_policy=None,
            output_ref=None,
        )


def test_run_node_idempotency_key_matches_spec() -> None:
    """The idempotency key formula for a RunNode matches 'attractor:<run_id>:<node_id>:attempt:<n>'."""
    run_node = RunNode(
        run_id="run1",
        node_id="plan",
        task_id=None,
        status=NodeRunStatus.PENDING,
        attempt=1,
        parent_node_ids=[],
        goal_gate_policy=None,
        output_ref=None,
    )
    key = IdempotencyKey.for_node(run_node.run_id, run_node.node_id, run_node.attempt)
    assert key.value == "attractor:run1:plan:attempt:1"
