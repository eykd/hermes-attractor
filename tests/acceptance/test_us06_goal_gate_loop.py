"""Acceptance tests for US6: Goal-gate routes back until satisfied.

Acceptance spec: specs/acceptance-specs/US06-goal-gate-loop.txt

Scenarios covered:

  1. Gate fail routes to retry_target with the next attempt number.
  2. Gate pass proceeds toward exit.
  3. Max attempts exhausted -> run transitions to BLOCKED.
  4. Missing/malformed gate verdict treated as fail (fail-secure).
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

pytestmark = pytest.mark.integration

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
_LATER = datetime.datetime(2026, 1, 1, second=10, tzinfo=datetime.UTC)


def _make_gate_pipeline(max_attempts: int = 3) -> Pipeline:
    """Build: start -> work -> gate -> exit (gate has retry_target=work).

    ``gate`` has a GoalGatePolicy that routes back to ``work`` on fail.
    """
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


def _make_run(run_id: str = "run1", status: RunStatus = RunStatus.RUNNING) -> Run:
    """Build a minimal Run."""
    return Run(
        run_id=run_id,
        spec_id="gate-pipeline",
        status=status,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_gate_record(
    task_id: str = "task-gate",
    attempt: int = 1,
    goal_gate: GoalGatePolicy | None = None,
) -> RunNode:
    """Build a gate RunNode."""
    return RunNode(
        run_id="run1",
        node_id="gate",
        task_id=task_id,
        status=NodeRunStatus.RUNNING,
        attempt=attempt,
        parent_node_ids=["work"],
        goal_gate_policy=goal_gate or GoalGatePolicy(retry_target="work", max_attempts=3),
    )


def test_gate_fail_routes_to_retry_target() -> None:
    """Gate fail routes to retry_target with a new attempt card.

    GIVEN a pipeline with a goal gate
    WHEN the gate card completes with gate=fail
    THEN a new card is created at the retry_target (work) with attempt:2.
    """
    pipeline = _make_gate_pipeline(max_attempts=3)
    run = _make_run()
    gate_record = _make_gate_record("task-gate", attempt=1)

    # There is 1 previous "work" node (attempt:1 was dispatched before this gate).
    prev_work_node = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["start"],
    )

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_record
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [prev_work_node, gate_record]

    created_cards: list[object] = []
    task_counter: list[int] = [10]

    def _create_card(card: object) -> str:
        """Record the card and return a unique task id."""
        created_cards.append(card)
        task_id = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        return task_id

    kanban = MagicMock()
    kanban.create_card.side_effect = _create_card
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-gate",
        event_id=2,
        event_kind="completed",
        summary="Gate failed.",
        metadata={},  # no "gate" field => fail-secure
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # A retry card should have been created at the retry_target (work).
    assert created_cards, "Expected a retry card to be created after gate fail"
    retry_card = created_cards[0]
    # The idempotency key should reference "work" node with attempt:2.
    key_value = retry_card.idempotency_key.value  # type: ignore[union-attr]
    assert "work" in key_value, f"Expected retry card at 'work' node, got key: {key_value}"
    assert "attempt:2" in key_value, f"Expected attempt:2 in idempotency key, got: {key_value}"


def test_gate_pass_proceeds_toward_exit() -> None:
    """Gate pass proceeds to the exit path.

    GIVEN a gate that explicitly passes
    WHEN the gate card completes with gate=pass
    THEN the run proceeds toward exit (not back to retry_target).
    """
    pipeline = _make_gate_pipeline(max_attempts=3)
    run = _make_run()
    gate_record = _make_gate_record("task-gate", attempt=1)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-gate",
        event_id=2,
        event_kind="completed",
        summary="Gate passed.",
        metadata={"gate": "pass"},  # explicit pass
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Run should be SUCCEEDED (gate -> exit).
    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.status is RunStatus.SUCCEEDED, f"Expected SUCCEEDED after gate pass, got {saved_run.status}"


def test_gate_max_attempts_exhausted_blocks_run() -> None:
    """Exhausting max_attempts transitions the run to BLOCKED.

    GIVEN a gate that has exhausted its max_attempts
    WHEN the gate card completes with gate=fail
    THEN the run transitions to BLOCKED and no further cards are created.
    """
    pipeline = _make_gate_pipeline(max_attempts=2)
    run = _make_run()
    # Two previous "work" nodes mean next_attempt=3 > max_attempts=2.
    gate_policy = GoalGatePolicy(retry_target="work", max_attempts=2)
    gate_record = _make_gate_record("task-gate", attempt=2, goal_gate=gate_policy)
    work_1 = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work-1",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["start"],
    )
    work_2 = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work-2",
        status=NodeRunStatus.SUCCEEDED,
        attempt=2,
        parent_node_ids=["gate"],
    )

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_record
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [work_1, work_2, gate_record]

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-gate",
        event_id=3,
        event_kind="completed",
        summary="Gate failed again.",
        metadata={},  # no gate field => fail-secure
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
    assert saved_run.status is RunStatus.BLOCKED, (
        f"Expected BLOCKED after max_attempts exhausted, got {saved_run.status}"
    )
    # No new cards should have been created.
    kanban.create_card.assert_not_called()


def test_gate_missing_gate_field_treated_as_fail() -> None:
    """Missing gate field in metadata is treated as fail (fail-secure).

    This is identical to test_gate_fail_routes_to_retry_target but makes the
    intent explicit: missing gate = fail, never pass.
    """
    pipeline = _make_gate_pipeline(max_attempts=3)
    run = _make_run()
    gate_record = _make_gate_record("task-gate", attempt=1)
    prev_work = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["start"],
    )

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_record
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [prev_work, gate_record]

    kanban = MagicMock()
    kanban.create_card.return_value = "task-retry"
    clock = MagicMock()
    clock.now.return_value = _LATER

    # No "gate" key in metadata.
    card_result = CardResult(
        task_id="task-gate",
        event_id=2,
        event_kind="completed",
        summary="Review done.",
        metadata={"reason": "needs more work"},  # no "gate" key
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Must not have reached SUCCEEDED (would mean it treated missing gate as pass).
    # A retry card should be created.
    kanban.create_card.assert_called()
    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.status is not RunStatus.SUCCEEDED, (
        "Missing gate field must not be treated as pass — run should not be SUCCEEDED"
    )
