"""Unit tests for the HUMAN node handler in advance_on_completion (RED phase M5 US4).

Tests fail because the PAUSED_HUMAN transition is not yet implemented in
src/hermes_attractor/use_cases/run_execution.py.
"""

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

    # Run must have been updated — either to RUNNING or directly to SUCCEEDED
    # (since human_review -> exit).
    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.status in (RunStatus.RUNNING, RunStatus.SUCCEEDED), (
        f"Expected RUNNING or SUCCEEDED after human input, got {saved_run.status}"
    )
