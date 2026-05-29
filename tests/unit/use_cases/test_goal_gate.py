"""Unit tests for goal gate loop logic in advance_on_completion (RED phase M4 US6).

These tests verify:
  1. gate=pass -> proceed to next node (toward exit)
  2. gate=fail -> new card at retry_target with attempt:n+1
  3. gate=fail at max_attempts -> run BLOCKED
  4. missing 'gate' field -> treated as fail (fail-secure)
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.card import CardResult
from hermes_attractor.domain.pipeline import (
    Context,
    Edge,
    GoalGatePolicy,
    Node,
    NodeShape,
    Pipeline,
    StyleRule,
    Stylesheet,
)
from hermes_attractor.domain.run import NodeRunStatus, Run, RunNode, RunStatus
from hermes_attractor.use_cases.run_execution import advance_on_completion

pytestmark = pytest.mark.unit

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
_LATER = datetime.datetime(2026, 1, 1, second=10, tzinfo=datetime.UTC)


def _make_gate_pipeline(max_attempts: int = 3) -> Pipeline:
    """Build: start -> work -> gate -> exit (gate routes back to work on fail)."""
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    gate = Node(
        node_id="gate",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="work", max_attempts=max_attempts),
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="gate"),
        Edge(source_id="gate", target_id="work", label="fail"),
        Edge(source_id="gate", target_id="exit", label="pass"),
    ]
    return Pipeline(
        spec_id="gate-pipeline",
        nodes=[start, work, gate, exit_],
        edges=edges,
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def _make_run(status: RunStatus = RunStatus.RUNNING) -> Run:
    """Build a minimal Run."""
    return Run(
        run_id="run1",
        spec_id="gate-pipeline",
        status=status,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_gate_node(attempt: int = 1, max_attempts: int = 3) -> RunNode:
    """Build a gate RunNode."""
    return RunNode(
        run_id="run1",
        node_id="gate",
        task_id="task-gate",
        status=NodeRunStatus.RUNNING,
        attempt=attempt,
        parent_node_ids=["work"],
        goal_gate_policy=GoalGatePolicy(retry_target="work", max_attempts=max_attempts),
    )


def _make_work_node(attempt: int = 1) -> RunNode:
    """Build a work RunNode with SUCCEEDED status."""
    return RunNode(
        run_id="run1",
        node_id="work",
        task_id=f"task-work-{attempt}",
        status=NodeRunStatus.SUCCEEDED,
        attempt=attempt,
        parent_node_ids=["start"],
    )


# ---------------------------------------------------------------------------
# Gate pass
# ---------------------------------------------------------------------------


def test_gate_pass_transitions_run_to_succeeded() -> None:
    """gate=pass causes run to proceed toward exit (SUCCEEDED)."""
    pipeline = _make_gate_pipeline()
    run = _make_run()
    gate_node = _make_gate_node(attempt=1)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_node
    run_state.get_run.return_value = run

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-gate",
        event_id=2,
        event_kind="completed",
        summary="Gate passed.",
        metadata={"gate": "pass"},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.status is RunStatus.SUCCEEDED


# ---------------------------------------------------------------------------
# Gate fail: route to retry target
# ---------------------------------------------------------------------------


def test_gate_fail_creates_retry_card_at_retry_target() -> None:
    """gate=fail creates a new card at retry_target with attempt:n+1."""
    pipeline = _make_gate_pipeline()
    run = _make_run()
    gate_node = _make_gate_node(attempt=1)
    prev_work = _make_work_node(attempt=1)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_node
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [prev_work, gate_node]

    kanban = MagicMock()
    kanban.create_card.return_value = "task-retry"
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-gate",
        event_id=2,
        event_kind="completed",
        summary="Gate failed.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    kanban.create_card.assert_called()
    retry_card = kanban.create_card.call_args[0][0]
    assert "work" in retry_card.idempotency_key.value
    assert "attempt:2" in retry_card.idempotency_key.value


def test_gate_fail_attempt_counter_increments_each_failure() -> None:
    """The attempt counter in the idempotency key increments on every gate failure."""
    pipeline = _make_gate_pipeline()
    run = _make_run()
    # Second gate attempt — there are 2 previous work nodes.
    gate_node = _make_gate_node(attempt=2)
    work_1 = _make_work_node(attempt=1)
    work_2 = _make_work_node(attempt=2)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_node
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [work_1, work_2, gate_node]

    kanban = MagicMock()
    kanban.create_card.return_value = "task-retry-3"
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-gate",
        event_id=3,
        event_kind="completed",
        summary="Gate failed again.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # 3rd attempt at work: prev_attempts=2, next_attempt=3.
    retry_card = kanban.create_card.call_args[0][0]
    assert "attempt:3" in retry_card.idempotency_key.value


# ---------------------------------------------------------------------------
# Gate exhaustion: BLOCKED
# ---------------------------------------------------------------------------


def test_gate_fail_at_max_attempts_blocks_run() -> None:
    """gate=fail at max_attempts causes run to transition to BLOCKED."""
    pipeline = _make_gate_pipeline(max_attempts=2)
    run = _make_run()
    gate_node = _make_gate_node(attempt=2, max_attempts=2)
    work_1 = _make_work_node(attempt=1)
    work_2 = _make_work_node(attempt=2)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_node
    run_state.get_run.return_value = run
    # Two previous work nodes means next_attempt=3 > max_attempts=2.
    run_state.nodes_for_run.return_value = [work_1, work_2, gate_node]

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-gate",
        event_id=4,
        event_kind="completed",
        summary="Gate failed — giving up.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.status is RunStatus.BLOCKED
    kanban.create_card.assert_not_called()


# ---------------------------------------------------------------------------
# Fail-secure: missing gate field
# ---------------------------------------------------------------------------


def test_missing_gate_field_treated_as_fail() -> None:
    """Missing 'gate' field in metadata is treated as gate fail (fail-secure)."""
    pipeline = _make_gate_pipeline()
    run = _make_run()
    gate_node = _make_gate_node(attempt=1)
    prev_work = _make_work_node(attempt=1)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_node
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [prev_work, gate_node]

    kanban = MagicMock()
    kanban.create_card.return_value = "task-retry"
    clock = MagicMock()
    clock.now.return_value = _LATER

    # Missing "gate" key in metadata.
    card_result = CardResult(
        task_id="task-gate",
        event_id=2,
        event_kind="completed",
        summary="Done.",
        metadata={"some_other_key": "value"},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Must have routed to retry (not succeeded).
    kanban.create_card.assert_called()
    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.status is not RunStatus.SUCCEEDED, "Missing gate field must not be treated as pass"
