"""Unit tests for the HUMAN node handler in advance_on_completion (RED phase M5 US4)."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.card import CardKind, CardResult
from hermes_attractor.domain.pipeline import (
    Context,
    Edge,
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


def _make_human_pipeline() -> Pipeline:
    """Build: start -> work -> human_review -> exit."""
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    human = Node(
        node_id="human_review",
        shape=NodeShape.HUMAN,
        profile="human",
        prompt="Please review: $summary.",
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="human_review"),
        Edge(source_id="human_review", target_id="exit"),
    ]
    return Pipeline(
        spec_id="human-pipeline",
        nodes=[start, work, human, exit_],
        edges=edges,
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def _make_run(
    run_id: str = "run1",
    status: RunStatus = RunStatus.RUNNING,
) -> Run:
    """Build a minimal Run."""
    return Run(
        run_id=run_id,
        spec_id="human-pipeline",
        status=status,
        context=Context(data={"summary": "work output"}),
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_run_node(
    node_id: str,
    task_id: str,
    status: NodeRunStatus = NodeRunStatus.DISPATCHED,
) -> RunNode:
    """Build a minimal RunNode."""
    return RunNode(
        run_id="run1",
        node_id=node_id,
        task_id=task_id,
        status=status,
        attempt=1,
        parent_node_ids=[],
    )


# ---------------------------------------------------------------------------
# HUMAN node: advance to PAUSED_HUMAN
# ---------------------------------------------------------------------------


def test_advance_on_human_node_creates_human_card_and_blocks_it() -> None:
    """advance_on_completion on a HUMAN node creates a HUMAN card and calls block_card."""
    pipeline = _make_human_pipeline()
    run = _make_run()
    # Simulate: work node just completed, work's RunNode is in the store.
    work_record = _make_run_node("work", "task-work", NodeRunStatus.RUNNING)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    kanban.create_card.return_value = "task-human"
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-work",
        event_id=1,
        event_kind="completed",
        summary="Work output.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # A HUMAN card must have been created.
    kanban.create_card.assert_called()
    created_card = kanban.create_card.call_args[0][0]
    assert created_card.kind is CardKind.HUMAN

    # block_card must have been called with the new human task id.
    kanban.block_card.assert_called_once()
    block_args = kanban.block_card.call_args
    assert block_args[0][0] == "task-human"  # positional task_id


def test_advance_on_human_node_transitions_run_to_paused_human() -> None:
    """advance_on_completion on a HUMAN node saves run with PAUSED_HUMAN status."""
    pipeline = _make_human_pipeline()
    run = _make_run()
    work_record = _make_run_node("work", "task-work", NodeRunStatus.RUNNING)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    kanban.create_card.return_value = "task-human"
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-work",
        event_id=1,
        event_kind="completed",
        summary="Work output.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # save_run must have been called with PAUSED_HUMAN status.
    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.status is RunStatus.PAUSED_HUMAN, f"Expected PAUSED_HUMAN after HUMAN node, got {saved_run.status}"


def test_advance_on_human_node_expands_prompt_in_block_body() -> None:
    """advance_on_completion expands $var placeholders in the HUMAN prompt for block_body."""
    pipeline = _make_human_pipeline()
    # Context has "summary" = "my output"
    run = Run(
        run_id="run1",
        spec_id="human-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={"summary": "my output"}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    work_record = _make_run_node("work", "task-work", NodeRunStatus.RUNNING)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    kanban.create_card.return_value = "task-human"
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-work",
        event_id=1,
        event_kind="completed",
        summary="Work output.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # block_card body should contain the expanded prompt.
    kanban.block_card.assert_called()
    block_kwargs = kanban.block_card.call_args[1]
    block_body = block_kwargs.get("body", "")
    assert "my output" in block_body, f"Expected expanded prompt in block body, got: {block_body!r}"


# ---------------------------------------------------------------------------
# HUMAN node: resume from PAUSED_HUMAN
# ---------------------------------------------------------------------------


def test_advance_on_completed_human_card_transitions_run_to_running() -> None:
    """When the human card completes, the run transitions back to RUNNING."""
    pipeline = _make_human_pipeline()
    # Run is PAUSED_HUMAN, human_review is DISPATCHED.
    run = _make_run(status=RunStatus.PAUSED_HUMAN)
    human_record = _make_run_node("human_review", "task-human", NodeRunStatus.DISPATCHED)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = human_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    # Next edge leads to EXIT — no new card created.
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-human",
        event_id=2,
        event_kind="completed",
        summary="Human approved.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Run must have transitioned to SUCCEEDED (human_review -> exit pipeline is deterministic).
    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.status is RunStatus.SUCCEEDED, (
        f"Expected SUCCEEDED after human card completes leading to EXIT, got {saved_run.status}"
    )


# ---------------------------------------------------------------------------
# HUMAN node: loop re-entry — attempt counter must not collide (bug fix)
# ---------------------------------------------------------------------------


def _make_loop_pipeline() -> Pipeline:
    """Build a pipeline that loops back to the HUMAN node.

    Topology: start -> coder -> human_review -> exit
    with an additional edge: coder -> human_review used on the second visit.
    In a real loop scenario the coder fires twice and must dispatch
    human_review at attempt=1 first, then attempt=2 on the second pass.
    For this test we represent the second coder pass directly:
    coder (task-coder-2) just completed, and human_review already has a
    SUCCEEDED RunNode from the first pass (attempt=1).
    """
    start = Node(node_id="start", shape=NodeShape.START)
    coder = Node(node_id="coder", shape=NodeShape.CODERGEN, profile="coder")
    human = Node(
        node_id="human_review",
        shape=NodeShape.HUMAN,
        profile="human",
        prompt="Review iteration $iteration.",
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="coder"),
        Edge(source_id="coder", target_id="human_review"),
        Edge(source_id="human_review", target_id="exit"),
    ]
    return Pipeline(
        spec_id="loop-pipeline",
        nodes=[start, coder, human, exit_],
        edges=edges,
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def test_human_node_loop_reentry_uses_incremented_attempt() -> None:
    """Second visit to the HUMAN node on a loop re-entry must use attempt=2.

    Bug: the old formula ``attempt = node_record.attempt + 1 if next_node.node_id ==
    node_record.node_id else 1`` always yields 1 for a loop (the condition only fires
    on a same-node self-loop, not a loop via other nodes).

    Fix: derive attempt from nodes_for_run count, matching the regular-node path.
    This test confirms:
    - The second HUMAN dispatch uses attempt=2 (not 1).
    - The IdempotencyKey for the second dispatch differs from the first.
    - The first RunNode (attempt=1, SUCCEEDED) is not overwritten.
    """
    pipeline = _make_loop_pipeline()

    # Second coder iteration just completed.
    coder_record_2 = RunNode(
        run_id="run1",
        node_id="coder",
        task_id="task-coder-2",
        status=NodeRunStatus.RUNNING,
        attempt=2,
        parent_node_ids=[],
    )
    # The first HUMAN visit is already SUCCEEDED (attempt=1).
    human_succeeded_1 = RunNode(
        run_id="run1",
        node_id="human_review",
        task_id="task-human-1",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["coder"],
    )

    run = Run(
        run_id="run1",
        spec_id="loop-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={"iteration": "2"}),
        created_at=_NOW,
        updated_at=_NOW,
    )

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = coder_record_2
    run_state.get_run.return_value = run
    # nodes_for_run returns all existing RunNodes including the SUCCEEDED human_review.
    run_state.nodes_for_run.return_value = [coder_record_2, human_succeeded_1]

    kanban = MagicMock()
    kanban.create_card.return_value = "task-human-2"
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-coder-2",
        event_id=10,
        event_kind="completed",
        summary="Second coder pass done.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # A HUMAN card must have been dispatched.
    kanban.create_card.assert_called_once()
    created_card = kanban.create_card.call_args[0][0]
    assert created_card.kind is CardKind.HUMAN

    # The idempotency key must use attempt=2.
    key = created_card.idempotency_key
    assert key.value.endswith(":attempt:2"), (
        f"Expected attempt=2 in idempotency key on loop re-entry, got: {key.value!r}"
    )

    # The RunNode written for the second HUMAN dispatch must use attempt=2.
    run_state.upsert_node.assert_called()
    upserted: RunNode = run_state.upsert_node.call_args[0][0]
    assert upserted.node_id == "human_review"
    assert upserted.attempt == 2, f"Expected attempt=2 for second HUMAN dispatch, got attempt={upserted.attempt}"
