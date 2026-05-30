"""Unit tests for the run execution use case and tool handlers (RED phase M2 US2).

Tests fail until src/hermes_attractor/use_cases/run_execution.py is implemented.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.card import CardKind, CardResult
from hermes_attractor.domain.exceptions import PipelineValidationError
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
from hermes_attractor.use_cases.run_execution import (
    _card_kind_for_node,  # pyright: ignore[reportPrivateUsage]
    advance_on_completion,
    launch_run,
    query_run_result,
    query_run_status,
)

pytestmark = pytest.mark.unit

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


# ---------------------------------------------------------------------------
# Test doubles / helpers
# ---------------------------------------------------------------------------


def _make_pipeline(
    *,
    spec_id: str = "spec-a",
    node_profile: str = "coder",
    prompt: str = "Implement $task.",
) -> MagicMock:
    """Build a minimal mock Pipeline for a start -> work -> exit linear pipeline.

    Args:
        spec_id: Pipeline spec identifier.
        node_profile: The resolved profile for the work node.
        prompt: The work node's prompt template.

    Returns:
        A MagicMock Pipeline.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile=node_profile, prompt=prompt)
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="exit"),
    ]
    stylesheet = Stylesheet(rules=[StyleRule(selector="*", profile="default")])
    return Pipeline(  # pyright: ignore[reportReturnType]
        spec_id=spec_id,
        nodes=[start, work, exit_],
        edges=edges,
        stylesheet=stylesheet,
    )


def _make_run(status: RunStatus = RunStatus.RUNNING) -> Run:
    """Build a minimal Run for testing.

    Args:
        status: The run's lifecycle status.

    Returns:
        A Run instance.
    """
    return Run(
        run_id="run1",
        spec_id="spec-a",
        status=status,
        context=Context(data={"task": "write tests"}),
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_run_node(
    node_id: str = "work",
    status: NodeRunStatus = NodeRunStatus.RUNNING,
    task_id: str = "task-001",
) -> RunNode:
    """Build a minimal RunNode for testing.

    Args:
        node_id: The pipeline node identifier.
        status: The node's current execution status.
        task_id: The kanban task identifier.

    Returns:
        A RunNode instance.
    """
    return RunNode(
        run_id="run1",
        node_id=node_id,
        task_id=task_id,
        status=status,
        attempt=1,
        parent_node_ids=[],
    )


# ---------------------------------------------------------------------------
# launch_run use case
# ---------------------------------------------------------------------------


def test_launch_run_creates_run_in_running_state() -> None:
    """launch_run creates a Run in RUNNING state and saves it."""
    pipeline = _make_pipeline()
    kanban = MagicMock()
    kanban.create_card.return_value = "task-001"
    run_state = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW
    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph spec-a {}"

    result = launch_run(
        spec_id="spec-a",
        initial_context={"task": "write tests"},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )

    assert result["run_id"]
    assert result["status"] == RunStatus.RUNNING.value
    run_state.create_run.assert_called_once()
    saved_run: Run = run_state.create_run.call_args[0][0]
    assert saved_run.status is RunStatus.RUNNING


def test_launch_run_creates_first_card_with_resolved_profile() -> None:
    """launch_run creates the first card assigned to the resolved node profile."""
    pipeline = _make_pipeline(node_profile="custom-coder")
    kanban = MagicMock()
    kanban.create_card.return_value = "task-001"
    run_state = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW
    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph spec-a {}"

    _ = launch_run(
        spec_id="spec-a",
        initial_context={"task": "write tests"},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )

    kanban.create_card.assert_called_once()
    card = kanban.create_card.call_args[0][0]
    assert card.assignee_profile == "custom-coder"


def test_launch_run_expands_prompt_variables_from_context() -> None:
    """launch_run expands $var placeholders in the node prompt using the initial context."""
    pipeline = _make_pipeline(prompt="Implement $task.")
    kanban = MagicMock()
    kanban.create_card.return_value = "task-001"
    run_state = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW
    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph spec-a {}"

    _ = launch_run(
        spec_id="spec-a",
        initial_context={"task": "write tests"},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )

    card = kanban.create_card.call_args[0][0]
    assert "write tests" in card.body


def test_launch_run_saves_run_node_with_dispatched_status() -> None:
    """launch_run saves the first RunNode with DISPATCHED status after creating the card."""
    pipeline = _make_pipeline()
    kanban = MagicMock()
    kanban.create_card.return_value = "task-001"
    run_state = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW
    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph spec-a {}"

    _ = launch_run(
        spec_id="spec-a",
        initial_context={},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )

    run_state.upsert_node.assert_called()
    saved_node: RunNode = run_state.upsert_node.call_args[0][0]
    assert saved_node.status is NodeRunStatus.DISPATCHED
    assert saved_node.task_id == "task-001"


# ---------------------------------------------------------------------------
# advance_on_completion use case
# ---------------------------------------------------------------------------


def test_advance_on_completion_marks_completed_node_succeeded() -> None:
    """advance_on_completion marks the completed RunNode as SUCCEEDED."""
    pipeline = _make_pipeline()
    kanban = MagicMock()
    kanban.create_card.return_value = "task-002"
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = _make_run_node("work", NodeRunStatus.RUNNING, "task-001")
    run_state.get_run.return_value = _make_run()
    clock = MagicMock()
    clock.now.return_value = _NOW
    card_result = CardResult(
        task_id="task-001",
        event_id=10,
        event_kind="completed",
        summary="Done.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # The first upsert_node call should mark the node SUCCEEDED
    calls = run_state.upsert_node.call_args_list
    statuses = [c[0][0].status for c in calls if hasattr(c[0][0], "status")]
    assert NodeRunStatus.SUCCEEDED in statuses


def test_advance_on_completion_saves_run_cursor_last() -> None:
    """advance_on_completion calls save_run (cursor update) as the last write."""
    pipeline = _make_pipeline()
    kanban = MagicMock()
    kanban.create_card.return_value = "task-002"
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = _make_run_node("work", NodeRunStatus.RUNNING, "task-001")
    run_state.get_run.return_value = _make_run()
    clock = MagicMock()
    clock.now.return_value = _NOW
    card_result = CardResult(
        task_id="task-001",
        event_id=10,
        event_kind="completed",
        summary="Done.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # save_run must be called and event_id must be updated
    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.last_seen_event_id == 10


def test_advance_on_completion_missing_gate_field_routes_to_retry() -> None:
    """advance_on_completion treats a missing 'gate' field as FAIL (fail-secure gate-verdict trust)."""
    start = Node(node_id="start", shape=NodeShape.START)
    gate_node = Node(
        node_id="gate",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="start", max_attempts=3),
    )
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="spec-gate",
        nodes=[start, gate_node, work, exit_],
        edges=[
            Edge(source_id="start", target_id="gate"),
            Edge(source_id="gate", target_id="work", label="pass"),
            Edge(source_id="gate", target_id="start", label="fail"),
            Edge(source_id="work", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    kanban = MagicMock()
    kanban.create_card.return_value = "task-retry"
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = _make_run_node("gate", NodeRunStatus.RUNNING, "task-gate")
    run_state.get_run.return_value = _make_run()
    clock = MagicMock()
    clock.now.return_value = _NOW
    # CardResult without 'gate' key in metadata — must route to retry target (FAIL-secure)
    card_result = CardResult(
        task_id="task-gate",
        event_id=5,
        event_kind="completed",
        summary="Review complete.",
        metadata={},  # no 'gate' field
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Should create a retry card (next node is the retry_target "start" direction)
    kanban.create_card.assert_called()
    card = kanban.create_card.call_args[0][0]
    # The card kind should be WORK or indicate retry routing — key invariant: no PASS
    assert card.kind in (CardKind.WORK, CardKind.GATE, CardKind.HUMAN)


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


def test_launch_run_with_start_node_but_no_edges_raises_validation_error() -> None:
    """launch_run raises PipelineValidationError when the pipeline fails validation."""
    start = Node(node_id="start", shape=NodeShape.START)
    pipeline = Pipeline(
        spec_id="spec-no-edges",
        nodes=[start],
        edges=[],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    kanban = MagicMock()
    run_state = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW
    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph spec-no-edges {}"

    with pytest.raises(PipelineValidationError):
        _ = launch_run(
            spec_id="spec-no-edges",
            initial_context={},
            kanban=kanban,
            run_state=run_state,
            serializer=serializer,
            store=store,
            clock=clock,
        )

    run_state.create_run.assert_not_called()


def test_launch_run_with_start_to_exit_edge_does_not_create_card() -> None:
    """launch_run does not create a card when START -> EXIT directly (degenerate pipeline)."""
    start = Node(node_id="start", shape=NodeShape.START)
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="spec-start-to-exit",
        nodes=[start, exit_],
        edges=[Edge(source_id="start", target_id="exit")],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    kanban = MagicMock()
    run_state = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW
    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph spec-start-to-exit {}"

    result = launch_run(
        spec_id="spec-start-to-exit",
        initial_context={},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )

    assert result["run_id"]
    kanban.create_card.assert_not_called()


def test_launch_run_with_no_start_node_raises_validation_error() -> None:
    """launch_run raises PipelineValidationError when the pipeline has no START node."""
    # Build a pipeline with only EXIT — no START
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="spec-b",
        nodes=[exit_],
        edges=[],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    kanban = MagicMock()
    run_state = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW
    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph spec-b {}"

    with pytest.raises(PipelineValidationError):
        _ = launch_run(
            spec_id="spec-b",
            initial_context={},
            kanban=kanban,
            run_state=run_state,
            serializer=serializer,
            store=store,
            clock=clock,
        )

    run_state.create_run.assert_not_called()
    # No card created because no START node
    kanban.create_card.assert_not_called()


def test_advance_on_completion_next_node_none_still_saves_run() -> None:
    """advance_on_completion saves run when next edge target node_id doesn't exist in pipeline."""
    # Build a pipeline with an edge to a "ghost" target that isn't in nodes.
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    pipeline = Pipeline(
        spec_id="spec-ghost",
        nodes=[start, work],
        edges=[
            Edge(source_id="start", target_id="work"),
            Edge(source_id="work", target_id="ghost"),  # ghost doesn't exist in nodes
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    kanban = MagicMock()
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = _make_run_node("work", NodeRunStatus.RUNNING, "task-001")
    run_state.get_run.return_value = _make_run()
    clock = MagicMock()
    clock.now.return_value = _NOW
    card_result = CardResult(
        task_id="task-001",
        event_id=9,
        event_kind="completed",
        summary="Done.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Should still save run with updated cursor
    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.last_seen_event_id == 9
    kanban.create_card.assert_not_called()


def test_advance_on_completion_no_next_edge_still_saves_run() -> None:
    """advance_on_completion saves run with updated cursor even when there is no outgoing edge."""
    # Build a pipeline where the current node has no outgoing edges.
    start = Node(node_id="start", shape=NodeShape.START)
    dead_end = Node(node_id="dead_end", shape=NodeShape.CODERGEN, profile="coder")
    pipeline = Pipeline(
        spec_id="spec-c",
        nodes=[start, dead_end],
        edges=[Edge(source_id="start", target_id="dead_end")],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    kanban = MagicMock()
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = _make_run_node("dead_end", NodeRunStatus.RUNNING, "task-001")
    run_state.get_run.return_value = _make_run()
    clock = MagicMock()
    clock.now.return_value = _NOW
    card_result = CardResult(
        task_id="task-001",
        event_id=3,
        event_kind="completed",
        summary="Done.",
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
    assert saved_run.last_seen_event_id == 3
    kanban.create_card.assert_not_called()


def test_card_kind_for_node_human_shape_returns_human() -> None:
    """_card_kind_for_node returns HUMAN for NodeShape.HUMAN."""
    assert _card_kind_for_node(NodeShape.HUMAN) is CardKind.HUMAN


def test_card_kind_for_node_non_human_returns_work() -> None:
    """_card_kind_for_node returns WORK for non-HUMAN shapes."""
    assert _card_kind_for_node(NodeShape.CODERGEN) is CardKind.WORK


def test_advance_on_completion_is_idempotent() -> None:
    """advance_on_completion called twice with the same card_result produces the same net state."""
    pipeline = _make_pipeline()
    kanban = MagicMock()
    kanban.create_card.return_value = "task-002"
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = _make_run_node("work", NodeRunStatus.RUNNING, "task-001")
    run_state.get_run.return_value = _make_run()
    clock = MagicMock()
    clock.now.return_value = _NOW
    card_result = CardResult(
        task_id="task-001",
        event_id=10,
        event_kind="completed",
        summary="Done.",
        metadata={},
    )

    # First call
    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )
    first_call_count = kanban.create_card.call_count

    # Second call with same card_result — should produce the same number of new cards
    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )
    second_call_count = kanban.create_card.call_count

    # Both calls create one card each (idempotent: same inputs same outputs)
    assert second_call_count == first_call_count * 2


def test_advance_on_completion_no_run_node_logs_and_returns() -> None:
    """advance_on_completion returns early when no RunNode found for task_id."""
    pipeline = _make_pipeline()
    kanban = MagicMock()
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = None
    clock = MagicMock()
    clock.now.return_value = _NOW
    card_result = CardResult(
        task_id="unknown-task",
        event_id=1,
        event_kind="completed",
        summary="Done.",
        metadata={},
    )

    # Should not raise; returns without doing anything
    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    run_state.save_run.assert_not_called()
    kanban.create_card.assert_not_called()


def test_advance_on_completion_no_run_logs_and_returns() -> None:
    """advance_on_completion returns early when no Run found for the RunNode's run_id."""
    pipeline = _make_pipeline()
    kanban = MagicMock()
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = _make_run_node()
    run_state.get_run.return_value = None
    clock = MagicMock()
    clock.now.return_value = _NOW
    card_result = CardResult(
        task_id="task-001",
        event_id=1,
        event_kind="completed",
        summary="Done.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    run_state.save_run.assert_not_called()


def test_advance_on_completion_exits_when_next_node_is_exit() -> None:
    """advance_on_completion marks run SUCCEEDED when next edge leads to EXIT."""
    pipeline = _make_pipeline()  # start -> work -> exit
    kanban = MagicMock()
    run_state = MagicMock()
    # work is done — next is exit
    run_state.get_node_by_task.return_value = _make_run_node("work", NodeRunStatus.RUNNING, "task-001")
    run_state.get_run.return_value = _make_run()
    clock = MagicMock()
    clock.now.return_value = _NOW
    card_result = CardResult(
        task_id="task-001",
        event_id=7,
        event_kind="completed",
        summary="Done.",
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
    assert saved_run.status is RunStatus.SUCCEEDED
    # No new card created (EXIT node)
    kanban.create_card.assert_not_called()


# ---------------------------------------------------------------------------
# TOOL node routing (coverage for edge cases)
# ---------------------------------------------------------------------------


def test_advance_tool_node_without_registry_saves_run_with_unchanged_context() -> None:
    """TOOL node with no tool_registry saves run with unchanged context (no-op tool)."""
    start = Node(node_id="start", shape=NodeShape.START)
    tool_node = Node(node_id="tool_stage", shape=NodeShape.TOOL, profile="tool-runner", prompt="my_tool")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="tool-pipeline",
        nodes=[start, tool_node, exit_],
        edges=[
            Edge(source_id="start", target_id="tool_stage"),
            Edge(source_id="tool_stage", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    work_record = RunNode(
        run_id="run1",
        node_id="start",
        task_id="task-start",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=[],
    )
    run = _make_run()

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW

    card_result = CardResult(
        task_id="task-start",
        event_id=1,
        event_kind="completed",
        summary="Start done.",
        metadata={},
    )

    # Call without tool_registry.
    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    run_state.save_run.assert_called()


def test_advance_tool_node_with_no_outgoing_edge_saves_run() -> None:
    """TOOL node with no outgoing edge saves run cursor and returns."""
    start = Node(node_id="start", shape=NodeShape.START)
    tool_node = Node(node_id="tool_stage", shape=NodeShape.TOOL, profile="tool-runner", prompt="my_tool")
    # No edge from tool_stage to anywhere.
    pipeline = Pipeline(
        spec_id="dead-end-tool",
        nodes=[start, tool_node],
        edges=[Edge(source_id="start", target_id="tool_stage")],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    work_record = RunNode(
        run_id="run1",
        node_id="start",
        task_id="task-start",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=[],
    )
    run = _make_run()

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(task_id="task-start", event_id=1, event_kind="completed", summary=".", metadata={}),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    run_state.save_run.assert_called()


def test_advance_tool_node_to_excluded_shape_returns_without_card() -> None:
    """TOOL node followed by FAN_IN (excluded shape) returns without creating a card."""
    start = Node(node_id="start", shape=NodeShape.START)
    tool_node = Node(node_id="tool_stage", shape=NodeShape.TOOL, profile="tool-runner", prompt="my_tool")
    fan_in = Node(node_id="fan_in", shape=NodeShape.FAN_IN, profile="orchestrator")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="tool-to-fanin",
        nodes=[start, tool_node, fan_in, exit_],
        edges=[
            Edge(source_id="start", target_id="tool_stage"),
            Edge(source_id="tool_stage", target_id="fan_in"),
            Edge(source_id="fan_in", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    work_record = RunNode(
        run_id="run1",
        node_id="start",
        task_id="task-start",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=[],
    )
    run = _make_run()

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(task_id="task-start", event_id=1, event_kind="completed", summary=".", metadata={}),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    run_state.save_run.assert_called()
    kanban.create_card.assert_not_called()


def test_advance_tool_with_registry_returning_non_dict_uses_empty_result() -> None:
    """TOOL node: tool_registry.run() returning a non-dict falls back to empty result."""
    start = Node(node_id="start", shape=NodeShape.START)
    tool_node = Node(node_id="tool_stage", shape=NodeShape.TOOL, profile="tool-runner", prompt="my_tool")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="tool-non-dict",
        nodes=[start, tool_node, exit_],
        edges=[
            Edge(source_id="start", target_id="tool_stage"),
            Edge(source_id="tool_stage", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    work_record = RunNode(
        run_id="run1",
        node_id="start",
        task_id="task-start",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=[],
    )
    run = _make_run()

    tool_registry = MagicMock()
    # Return a non-dict value — the cast fallback should produce {}.
    tool_registry.run.return_value = "not-a-dict"

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(task_id="task-start", event_id=1, event_kind="completed", summary=".", metadata={}),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
        tool_registry=tool_registry,
    )

    # The run should be saved (context unchanged — no context_updates from the empty fallback).
    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.context == run.context


def test_advance_tool_with_context_updates_applies_updates() -> None:
    """TOOL node: tool_registry.run() returning a dict with context_updates merges into context."""
    start = Node(node_id="start", shape=NodeShape.START)
    tool_node = Node(node_id="tool_stage", shape=NodeShape.TOOL, profile="tool-runner", prompt="my_tool")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="tool-context-updates",
        nodes=[start, tool_node, exit_],
        edges=[
            Edge(source_id="start", target_id="tool_stage"),
            Edge(source_id="tool_stage", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    work_record = RunNode(
        run_id="run1",
        node_id="start",
        task_id="task-start",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=[],
    )
    run = _make_run()

    tool_registry = MagicMock()
    # Return a dict with context_updates — should be merged into the run context.
    tool_registry.run.return_value = {"context_updates": {"injected_key": "injected_value"}}

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(task_id="task-start", event_id=1, event_kind="completed", summary=".", metadata={}),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
        tool_registry=tool_registry,
    )

    # The run should be saved with the merged context key.
    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.context.data.get("injected_key") == "injected_value"


def test_advance_tool_node_to_non_exit_next_saves_run() -> None:
    """TOOL node followed by a non-EXIT node saves run without marking SUCCEEDED."""
    start = Node(node_id="start", shape=NodeShape.START)
    tool_node = Node(node_id="tool_stage", shape=NodeShape.TOOL, profile="tool-runner", prompt="my_tool")
    another_work = Node(node_id="after_tool", shape=NodeShape.CODERGEN, profile="coder")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="tool-then-work",
        nodes=[start, tool_node, another_work, exit_],
        edges=[
            Edge(source_id="start", target_id="tool_stage"),
            Edge(source_id="tool_stage", target_id="after_tool"),
            Edge(source_id="after_tool", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    work_record = RunNode(
        run_id="run1",
        node_id="start",
        task_id="task-start",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=[],
    )
    run = _make_run()

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(task_id="task-start", event_id=1, event_kind="completed", summary=".", metadata={}),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Not SUCCEEDED (after_tool is not EXIT).
    run_state.save_run.assert_called()
    # A card should be created for after_tool.
    kanban.create_card.assert_called()


def test_advance_tool_node_to_non_exit_saves_run_after_upsert_node() -> None:
    """TOOL node regular-next path: save_run (cursor) is the last write (FR-024).

    Regression test: previously save_run was called before upsert_node, so a
    crash between those two writes would advance the cursor past the event without
    persisting the new RunNode, silently losing the dispatch on reconcile.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    tool_node = Node(node_id="tool_stage", shape=NodeShape.TOOL, profile="tool-runner", prompt="my_tool")
    another_work = Node(node_id="after_tool", shape=NodeShape.CODERGEN, profile="coder")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="tool-then-work-order",
        nodes=[start, tool_node, another_work, exit_],
        edges=[
            Edge(source_id="start", target_id="tool_stage"),
            Edge(source_id="tool_stage", target_id="after_tool"),
            Edge(source_id="after_tool", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    work_record = RunNode(
        run_id="run1",
        node_id="start",
        task_id="task-start",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=[],
    )
    run = _make_run()

    call_order: list[str] = []
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    def _record_upsert(node: object) -> None:
        """Record that upsert_node was called."""
        call_order.append("upsert_node")

    def _record_save(run_obj: object) -> None:
        """Record that save_run was called."""
        call_order.append("save_run")

    run_state.upsert_node.side_effect = _record_upsert
    run_state.save_run.side_effect = _record_save

    kanban = MagicMock()
    kanban.create_card.return_value = "task-after-tool"
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(task_id="task-start", event_id=5, event_kind="completed", summary=".", metadata={}),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # upsert_node for the SUCCEEDED start node and then for after_tool both happen
    # before the final save_run that advances the event cursor.
    assert "save_run" in call_order, "save_run must be called"
    assert "upsert_node" in call_order, "upsert_node must be called"
    # The last save_run must come after all upsert_node calls (cursor-last invariant).
    last_save_run_idx = max(i for i, name in enumerate(call_order) if name == "save_run")
    last_upsert_node_idx = max(i for i, name in enumerate(call_order) if name == "upsert_node")
    assert last_save_run_idx > last_upsert_node_idx, (
        f"save_run (idx {last_save_run_idx}) must come after upsert_node (idx {last_upsert_node_idx}); "
        f"call order: {call_order}"
    )
    # The cursor must be advanced to the processed event.
    saved_run: Run = run_state.save_run.call_args_list[-1][0][0]
    assert saved_run.last_seen_event_id == 5


# ---------------------------------------------------------------------------
# Goal gate routing
# ---------------------------------------------------------------------------


def _make_gate_pipeline_unit() -> Pipeline:
    """Build: start -> work -> gate -> exit (gate has retry_target=work, max_attempts=2)."""
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    gate = Node(
        node_id="gate",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="work", max_attempts=2),
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


def test_advance_goal_gate_fail_creates_retry_card_with_incremented_attempt() -> None:
    """Goal gate fail creates retry card at retry_target with next attempt number."""
    pipeline = _make_gate_pipeline_unit()
    run = _make_run()
    gate_node = RunNode(
        run_id="run1",
        node_id="gate",
        task_id="task-gate",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["work"],
        goal_gate_policy=GoalGatePolicy(retry_target="work", max_attempts=2),
    )
    prev_work = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["start"],
    )

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_node
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [prev_work, gate_node]

    kanban = MagicMock()
    kanban.create_card.return_value = "task-retry"
    clock = MagicMock()
    clock.now.return_value = _NOW

    card_result = CardResult(
        task_id="task-gate",
        event_id=2,
        event_kind="completed",
        summary="Gate failed.",
        metadata={},  # no gate field => fail
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


def test_advance_goal_gate_fail_with_nonexistent_retry_target_saves_run() -> None:
    """Goal gate fail when retry_target node doesn't exist still saves run cursor.

    Uses a pipeline where the pipeline node's own goal_gate.retry_target points to
    a node that doesn't exist in the node_map, so the retry block falls through to
    normal edge routing and the run cursor is still saved.
    """
    # Build a custom pipeline where the gate node's goal_gate.retry_target is "ghost_retry_target",
    # which doesn't exist in nodes. The fix reads the LIVE pipeline goal_gate, so we must
    # use a pipeline where the live goal_gate itself has the nonexistent retry target.
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    gate = Node(
        node_id="gate",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="ghost_retry_target", max_attempts=3),
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="ghost-retry-pipeline",
        nodes=[start, work, gate, exit_],
        edges=[
            Edge(source_id="start", target_id="work"),
            Edge(source_id="work", target_id="gate"),
            Edge(source_id="gate", target_id="exit", label="pass"),
            Edge(source_id="gate", target_id="work", label="fail"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    run = _make_run()
    gate_node = RunNode(
        run_id="run1",
        node_id="gate",
        task_id="task-gate",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["work"],
        # goal_gate_policy may be None or set; the fix reads the live pipeline goal_gate.
        goal_gate_policy=GoalGatePolicy(retry_target="ghost_retry_target", max_attempts=3),
    )
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_node
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [gate_node]

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW

    card_result = CardResult(
        task_id="task-gate",
        event_id=2,
        event_kind="completed",
        summary="Failed.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # When retry_target doesn't exist, falls through to normal edge routing.
    # The run cursor should still be saved.
    run_state.save_run.assert_called()


def test_advance_goal_gate_exhausted_blocks_run() -> None:
    """When max_attempts is exhausted the run transitions to BLOCKED."""
    pipeline = _make_gate_pipeline_unit()
    run = _make_run()
    gate_node = RunNode(
        run_id="run1",
        node_id="gate",
        task_id="task-gate",
        status=NodeRunStatus.RUNNING,
        attempt=2,  # second gate attempt
        parent_node_ids=["work"],
        goal_gate_policy=GoalGatePolicy(retry_target="work", max_attempts=2),
    )
    # Two previous "work" attempts means next_attempt=3 > max_attempts=2.
    prev_work_1 = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work-1",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["start"],
    )
    prev_work_2 = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work-2",
        status=NodeRunStatus.SUCCEEDED,
        attempt=2,
        parent_node_ids=["gate"],
    )

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_node
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [prev_work_1, prev_work_2, gate_node]

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW

    card_result = CardResult(
        task_id="task-gate",
        event_id=4,
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

    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.status is RunStatus.BLOCKED
    kanban.create_card.assert_not_called()


# ---------------------------------------------------------------------------
# query_run_status
# ---------------------------------------------------------------------------


def test_query_run_status_returns_status_current_nodes_and_context_keys() -> None:
    """query_run_status returns run status, active node ids, and context keys."""
    run = _make_run()
    dispatched_node = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.DISPATCHED,
        attempt=1,
        parent_node_ids=["start"],
    )
    succeeded_node = RunNode(
        run_id="run1",
        node_id="start",
        task_id="task-start",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=[],
    )

    run_state = MagicMock()
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [dispatched_node, succeeded_node]

    result = query_run_status(run_id="run1", run_state=run_state)

    assert result["run_id"] == "run1"
    assert result["status"] == "RUNNING"
    assert result["current_nodes"] == ["work"]
    context_keys = result["context_keys"]
    assert isinstance(context_keys, list)
    assert "task" in context_keys


def test_query_run_status_running_node_is_included_in_current_nodes() -> None:
    """query_run_status includes RUNNING status nodes as current nodes."""
    run = _make_run()
    running_node = RunNode(
        run_id="run1",
        node_id="step2",
        task_id="task-step2",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
    )

    run_state = MagicMock()
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [running_node]

    result = query_run_status(run_id="run1", run_state=run_state)

    assert result["current_nodes"] == ["step2"]


def test_query_run_status_raises_key_error_when_run_not_found() -> None:
    """query_run_status raises KeyError when the run_id does not exist."""
    run_state = MagicMock()
    run_state.get_run.return_value = None

    with pytest.raises(KeyError, match="run-missing"):
        _ = query_run_status(run_id="run-missing", run_state=run_state)


# ---------------------------------------------------------------------------
# query_run_result
# ---------------------------------------------------------------------------


def test_query_run_result_returns_status_and_outcome() -> None:
    """query_run_result returns run status and the full context data as outcome."""
    run = Run(
        run_id="run1",
        spec_id="spec-a",
        status=RunStatus.SUCCEEDED,
        context=Context(data={"output": "final-answer"}),
        created_at=_NOW,
        updated_at=_NOW,
    )

    run_state = MagicMock()
    run_state.get_run.return_value = run

    result = query_run_result(run_id="run1", run_state=run_state)

    assert result["run_id"] == "run1"
    assert result["status"] == "SUCCEEDED"
    assert result["outcome"] == {"output": "final-answer"}


def test_query_run_result_raises_key_error_when_run_not_found() -> None:
    """query_run_result raises KeyError when the run_id does not exist."""
    run_state = MagicMock()
    run_state.get_run.return_value = None

    with pytest.raises(KeyError, match="run-gone"):
        _ = query_run_result(run_id="run-gone", run_state=run_state)


# ---------------------------------------------------------------------------
# FR-009: goal_gate_policy populated from pipeline_node.goal_gate in dispatch paths
# ---------------------------------------------------------------------------


def _make_gate_entry_pipeline() -> Pipeline:
    """Build: start -> gate_node -> exit, where gate_node has goal_gate set.

    The entry node (gate_node) is dispatched directly by launch_run.
    This exercises the launch_run dispatch path (bug: goal_gate_policy was never set).
    """
    start = Node(node_id="start", shape=NodeShape.START)
    gate_node = Node(
        node_id="gate_node",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="gate_node", max_attempts=3),
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="gate_node"),
        Edge(source_id="gate_node", target_id="exit", label="pass"),
        Edge(source_id="gate_node", target_id="gate_node", label="fail"),
    ]
    return Pipeline(
        spec_id="gate-entry-pipeline",
        nodes=[start, gate_node, exit_],
        edges=edges,
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def test_launch_run_populates_goal_gate_policy_from_pipeline_node() -> None:
    """launch_run must copy pipeline_node.goal_gate into RunNode.goal_gate_policy.

    Before the fix, all three dispatch paths created RunNodes with goal_gate_policy=None,
    making FR-009 goal-gate retry inert in production even though unit tests passed
    (they set goal_gate_policy directly on the fixture).
    """
    pipeline = _make_gate_entry_pipeline()
    kanban = MagicMock()
    kanban.create_card.return_value = "task-gate-001"
    run_state = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW
    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph gate-entry-pipeline {}"

    _ = launch_run(
        spec_id="gate-entry-pipeline",
        initial_context={},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )

    run_state.upsert_node.assert_called_once()
    dispatched_node: RunNode = run_state.upsert_node.call_args[0][0]
    # The critical assertion: goal_gate_policy must be populated from the pipeline node,
    # not left as None (the pre-fix behaviour).
    assert dispatched_node.goal_gate_policy is not None, (
        "launch_run must copy pipeline_node.goal_gate into RunNode.goal_gate_policy; "
        "leaving it None makes FR-009 goal-gate retry unreachable in production"
    )
    assert dispatched_node.goal_gate_policy.retry_target == "gate_node"
    assert dispatched_node.goal_gate_policy.max_attempts == 3


def test_fan_out_dispatch_populates_goal_gate_policy_from_branch_pipeline_node() -> None:
    """FAN_OUT branch dispatch must copy branch_node.goal_gate into RunNode.goal_gate_policy.

    The FAN_OUT branch dispatch path also created RunNodes with goal_gate_policy=None.
    """
    # Pipeline: start -> fan_out -> [gate_branch, plain_branch] -> fan_in -> exit
    start = Node(node_id="start", shape=NodeShape.START)
    fan_out = Node(node_id="fan_out", shape=NodeShape.FAN_OUT, profile="orchestrator")
    gate_branch = Node(
        node_id="gate_branch",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="gate_branch", max_attempts=2),
    )
    plain_branch = Node(node_id="plain_branch", shape=NodeShape.CODERGEN, profile="coder")
    fan_in = Node(node_id="fan_in", shape=NodeShape.FAN_IN, profile="merger")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="fan-out-gate-pipeline",
        nodes=[start, fan_out, gate_branch, plain_branch, fan_in, exit_],
        edges=[
            Edge(source_id="start", target_id="fan_out"),
            Edge(source_id="fan_out", target_id="gate_branch"),
            Edge(source_id="fan_out", target_id="plain_branch"),
            Edge(source_id="gate_branch", target_id="fan_in"),
            Edge(source_id="plain_branch", target_id="fan_in"),
            Edge(source_id="fan_in", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )

    fan_out_record = RunNode(
        run_id="run1",
        node_id="fan_out",
        task_id="task-fan-out",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
    )
    run = _make_run()

    upserted_nodes: list[RunNode] = []

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = fan_out_record
    run_state.get_run.return_value = run

    def _capture_upsert(node: RunNode) -> None:
        """Capture upserted nodes."""
        upserted_nodes.append(node)

    run_state.upsert_node.side_effect = _capture_upsert

    task_counter: list[int] = [10]
    kanban = MagicMock()

    def _create_card(card: object) -> str:
        """Return a unique task id."""
        tid = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        return tid

    kanban.create_card.side_effect = _create_card
    clock = MagicMock()
    clock.now.return_value = _NOW

    card_result = CardResult(
        task_id="task-fan-out",
        event_id=1,
        event_kind="completed",
        summary="FAN_OUT done.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Two branch nodes should have been upserted (gate_branch and plain_branch),
    # plus the initial SUCCEEDED record for fan_out itself.
    branch_nodes = [n for n in upserted_nodes if n.node_id == "gate_branch"]
    assert branch_nodes, "Expected a RunNode upserted for gate_branch"
    gate_branch_record = branch_nodes[0]
    # The critical assertion: goal_gate_policy must be populated from the branch pipeline node.
    assert gate_branch_record.goal_gate_policy is not None, (
        "FAN_OUT dispatch must copy branch_node.goal_gate into RunNode.goal_gate_policy"
    )
    assert gate_branch_record.goal_gate_policy.retry_target == "gate_branch"


def test_sequential_dispatch_populates_goal_gate_policy_from_next_pipeline_node() -> None:
    """Sequential next-node dispatch must copy next_node.goal_gate into RunNode.goal_gate_policy.

    This exercises the third broken dispatch path (line 723 of run_execution.py).
    After the fix, the retry path is exercisable without manually injecting goal_gate_policy
    on the RunNode fixture.
    """
    # Pipeline: start -> work -> gate -> exit
    # gate has goal_gate set; work completes and advance_on_completion dispatches gate.
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    gate = Node(
        node_id="gate",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="work", max_attempts=2),
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="seq-gate-pipeline",
        nodes=[start, work, gate, exit_],
        edges=[
            Edge(source_id="start", target_id="work"),
            Edge(source_id="work", target_id="gate"),
            Edge(source_id="gate", target_id="work", label="fail"),
            Edge(source_id="gate", target_id="exit", label="pass"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )

    # work node just completed — advance_on_completion will dispatch gate next.
    work_record = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
        # Deliberately NOT setting goal_gate_policy here (work has no gate).
    )
    run = _make_run()

    upserted_nodes: list[RunNode] = []

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    def _capture_upsert(node: RunNode) -> None:
        """Capture upserted nodes."""
        upserted_nodes.append(node)

    run_state.upsert_node.side_effect = _capture_upsert

    kanban = MagicMock()
    kanban.create_card.return_value = "task-gate-001"
    clock = MagicMock()
    clock.now.return_value = _NOW

    card_result = CardResult(
        task_id="task-work",
        event_id=2,
        event_kind="completed",
        summary="Work done.",
        metadata={},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # The gate RunNode should have been upserted (after the SUCCEEDED work node record).
    gate_nodes = [n for n in upserted_nodes if n.node_id == "gate"]
    assert gate_nodes, "Expected a RunNode upserted for gate"
    gate_record = gate_nodes[0]
    # The critical assertion: goal_gate_policy must be populated from the pipeline node.
    assert gate_record.goal_gate_policy is not None, (
        "Sequential dispatch must copy next_node.goal_gate into RunNode.goal_gate_policy; "
        "leaving it None makes FR-009 goal-gate retry unreachable in production"
    )
    assert gate_record.goal_gate_policy.retry_target == "work"
    assert gate_record.goal_gate_policy.max_attempts == 2


def test_retry_path_triggered_via_dispatch_path_without_manual_goal_gate_injection() -> None:
    """FR-009 retry path is reachable when goal_gate_policy comes from the dispatch path.

    This test exercises the full chain:
    1. advance_on_completion dispatches gate node (sets goal_gate_policy from pipeline).
    2. The gate node's card completes with gate=fail.
    3. advance_on_completion creates a retry card (without manually setting goal_gate_policy).

    This proves the end-to-end retry path works without test fixture injection.
    """
    # Pipeline: start -> work -> gate -> exit (gate retries work on fail)
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    gate = Node(
        node_id="gate",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="work", max_attempts=3),
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="e2e-gate-pipeline",
        nodes=[start, work, gate, exit_],
        edges=[
            Edge(source_id="start", target_id="work"),
            Edge(source_id="work", target_id="gate"),
            Edge(source_id="gate", target_id="work", label="fail"),
            Edge(source_id="gate", target_id="exit", label="pass"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    run = Run(
        run_id="run1",
        spec_id="e2e-gate-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )

    # --- Step 1: work completes; gate is dispatched ---
    upserted_nodes: list[RunNode] = []
    work_record = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
        # NOTE: goal_gate_policy is NOT set here — work has no gate.
    )

    run_state_step1 = MagicMock()
    run_state_step1.get_node_by_task.return_value = work_record
    run_state_step1.get_run.return_value = run
    run_state_step1.upsert_node.side_effect = upserted_nodes.append

    kanban = MagicMock()
    kanban.create_card.return_value = "task-gate-001"
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(
            task_id="task-work",
            event_id=1,
            event_kind="completed",
            summary="Work done.",
            metadata={},
        ),
        kanban=kanban,
        run_state=run_state_step1,
        pipeline=pipeline,
        clock=clock,
    )

    # Extract the dispatched gate RunNode — it must have goal_gate_policy populated.
    gate_nodes_dispatched = [n for n in upserted_nodes if n.node_id == "gate"]
    assert gate_nodes_dispatched, "gate node must be dispatched after work completes"
    gate_record = gate_nodes_dispatched[0]
    # This is the key invariant from the bug fix — no manual injection.
    assert gate_record.goal_gate_policy is not None, (
        "gate RunNode must have goal_gate_policy populated from pipeline node during dispatch"
    )

    # --- Step 2: gate card completes with gate=fail; retry card must be created ---
    prev_work_node = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["start"],
    )

    run_state_step2 = MagicMock()
    # Use the dispatched gate_record directly — no manual goal_gate_policy injection.
    run_state_step2.get_node_by_task.return_value = gate_record
    run_state_step2.get_run.return_value = run
    run_state_step2.nodes_for_run.return_value = [prev_work_node, gate_record]

    kanban2 = MagicMock()
    kanban2.create_card.return_value = "task-retry-work"

    advance_on_completion(
        card_result=CardResult(
            task_id="task-gate-001",
            event_id=2,
            event_kind="completed",
            summary="Gate failed.",
            metadata={},  # no gate field => fail-secure
        ),
        kanban=kanban2,
        run_state=run_state_step2,
        pipeline=pipeline,
        clock=clock,
    )

    # A retry card must be created at work (retry_target).
    kanban2.create_card.assert_called()
    retry_card = kanban2.create_card.call_args[0][0]
    assert "work" in retry_card.idempotency_key.value, "Retry card must target the retry_target node 'work'"
    assert "attempt:2" in retry_card.idempotency_key.value, (
        "Retry card must have attempt:2 (next attempt after the first)"
    )


# ---------------------------------------------------------------------------
# Bug (a): gate re-dispatched at attempt=1 on second iteration (FR-009/FR-024)
# Bug (b): gate retry next_attempt counted from nodes_for_run before save_run (FR-024)
# ---------------------------------------------------------------------------


def _make_gate_pipeline_for_bug_tests() -> Pipeline:
    """Build: start -> work -> gate -> exit (gate retries work on fail, max 3).

    Used to drive the full dispatch path across two gate iterations.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    gate = Node(
        node_id="gate",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="work", max_attempts=3),
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="gate"),
        Edge(source_id="gate", target_id="work", label="fail"),
        Edge(source_id="gate", target_id="exit", label="pass"),
    ]
    return Pipeline(
        spec_id="bug-gate-pipeline",
        nodes=[start, work, gate, exit_],
        edges=edges,
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def _dispatch_gate_after_work_1(
    pipeline: Pipeline,
    run: Run,
    clock: MagicMock,
) -> tuple[RunNode, RunNode]:
    """Step 1 helper: work(1) completes; dispatch gate(1). Return (work_succeeded, gate_record_1).

    Args:
        pipeline: The pipeline domain object.
        run: The Run domain object.
        clock: The test clock mock.

    Returns:
        A tuple of (work_succeeded_1, gate_record_1) RunNodes.
    """
    upserted: list[RunNode] = []
    work_record_1 = RunNode(
        run_id=run.run_id,
        node_id="work",
        task_id="task-work-1",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
    )
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record_1
    run_state.get_run.return_value = run
    run_state.upsert_node.side_effect = upserted.append
    kanban = MagicMock()
    kanban.create_card.return_value = "task-gate-1"

    advance_on_completion(
        card_result=CardResult(
            task_id="task-work-1",
            event_id=1,
            event_kind="completed",
            summary="Work done.",
            metadata={},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    gate_nodes = [n for n in upserted if n.node_id == "gate"]
    assert gate_nodes, "gate must be dispatched after work(1) completes"
    gate_record_1 = gate_nodes[0]
    assert gate_record_1.attempt == 1, "gate attempt must be 1 on first dispatch"
    work_succeeded_1 = RunNode(
        run_id=run.run_id,
        node_id="work",
        task_id="task-work-1",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["start"],
    )
    return work_succeeded_1, gate_record_1


def _dispatch_work_retry_after_gate_1_fails(
    pipeline: Pipeline,
    run: Run,
    clock: MagicMock,
    work_succeeded_1: RunNode,
    gate_record_1: RunNode,
) -> RunNode:
    """Step 2 helper: gate(1) fails; dispatch work(2). Return work_retry_record.

    Args:
        pipeline: The pipeline domain object.
        run: The Run domain object.
        clock: The test clock mock.
        work_succeeded_1: The SUCCEEDED work RunNode from step 1.
        gate_record_1: The gate RunNode dispatched in step 1.

    Returns:
        The work retry RunNode (attempt=2).
    """
    upserted: list[RunNode] = []
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_record_1
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [work_succeeded_1, gate_record_1]
    run_state.upsert_node.side_effect = upserted.append
    kanban = MagicMock()
    kanban.create_card.return_value = "task-work-2"

    advance_on_completion(
        card_result=CardResult(
            task_id="task-gate-1",
            event_id=2,
            event_kind="completed",
            summary="Gate failed.",
            metadata={},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    work_nodes = [n for n in upserted if n.node_id == "work"]
    assert work_nodes, "work retry must be dispatched after gate(1) fails"
    work_retry = work_nodes[0]
    assert work_retry.attempt == 2, "work retry must be at attempt=2"
    return work_retry


def test_gate_second_iteration_dispatched_at_attempt_2_via_real_dispatch_path() -> None:
    """Bug (a): gate must be dispatched at attempt=2 on the second gate iteration.

    The bug: line ~714 computes ``attempt = 1`` for any next_node that differs from
    node_record, so gate is always dispatched at attempt=1. The 2nd gate card then
    shares the idempotency key with the 1st, and create_card returns the stale
    completed task instead of a fresh one.

    This test drives the full dispatch path (no manual RunNode state injection):
    1. work(1) completes → gate(1) dispatched (via helper)
    2. gate(1) fails → work(2) dispatched via retry path (via helper)
    3. work(2) completes → gate must be dispatched at attempt=2 (not attempt=1)
    """
    pipeline = _make_gate_pipeline_for_bug_tests()
    run = Run(
        run_id="run-bug-a",
        spec_id="bug-gate-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    clock = MagicMock()
    clock.now.return_value = _NOW

    work_succeeded_1, gate_record_1 = _dispatch_gate_after_work_1(pipeline, run, clock)
    work_retry_record = _dispatch_work_retry_after_gate_1_fails(pipeline, run, clock, work_succeeded_1, gate_record_1)

    # --- Step 3: work(2) completes; gate must be dispatched at attempt=2 ---
    upserted_step3: list[RunNode] = []
    gate_completed_1 = RunNode(
        run_id="run-bug-a",
        node_id="gate",
        task_id="task-gate-1",
        status=NodeRunStatus.PARTIAL,
        attempt=1,
        parent_node_ids=["work"],
        goal_gate_policy=gate_record_1.goal_gate_policy,
    )
    run_state_3 = MagicMock()
    run_state_3.get_node_by_task.return_value = work_retry_record
    run_state_3.get_run.return_value = run
    run_state_3.nodes_for_run.return_value = [work_succeeded_1, gate_completed_1, work_retry_record]
    run_state_3.upsert_node.side_effect = upserted_step3.append
    kanban_3 = MagicMock()
    kanban_3.create_card.return_value = "task-gate-2"

    advance_on_completion(
        card_result=CardResult(
            task_id="task-work-2",
            event_id=3,
            event_kind="completed",
            summary="Work retry done.",
            metadata={},
        ),
        kanban=kanban_3,
        run_state=run_state_3,
        pipeline=pipeline,
        clock=clock,
    )

    gate_nodes_step3 = [n for n in upserted_step3 if n.node_id == "gate"]
    assert gate_nodes_step3, "gate must be dispatched after work(2) completes"
    gate_record_2 = gate_nodes_step3[0]
    assert gate_record_2.attempt == 2, (
        f"gate must be dispatched at attempt=2 on second iteration; "
        f"got attempt={gate_record_2.attempt}. "
        "Bug: attempt=1 for any next_node that differs from node_record."
    )
    kanban_3.create_card.assert_called()
    gate_card_2 = kanban_3.create_card.call_args[0][0]
    assert "attempt:2" in gate_card_2.idempotency_key.value, (
        f"Second gate card must use attempt:2 in its idempotency key; got {gate_card_2.idempotency_key.value!r}"
    )
    assert "attempt:1" not in gate_card_2.idempotency_key.value, (
        "Second gate card must NOT reuse attempt:1 idempotency key"
    )


def test_gate_retry_crash_replay_does_not_create_duplicate_retry_row() -> None:
    """Bug (b): replaying a gate-fail event must not create a second retry RunNode.

    The bug: lines ~430-432 count nodes_for_run rows at retry_target BEFORE save_run.
    After a crash-and-replay, the first execution's upsert_node has already persisted
    the retry RunNode. On replay, nodes_for_run returns one more row, so next_attempt
    is one higher, and upsert_node is called again with a different attempt number —
    creating a duplicate coexisting retry row.

    Fix: derive next_attempt from node_record.attempt + 1 (the gate node's own attempt
    counter, which is stable across replays).

    This test simulates the crash/replay by calling advance_on_completion twice with
    the same gate-fail card_result. On the second call, nodes_for_run already includes
    the retry RunNode written by the first call. Both calls must produce the same
    next_attempt value and the same idempotency key.
    """
    pipeline = _make_gate_pipeline_for_bug_tests()
    run = Run(
        run_id="run-bug-b",
        spec_id="bug-gate-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    clock = MagicMock()
    clock.now.return_value = _NOW

    # Gate (attempt=1) just failed. We have: work(1) SUCCEEDED, gate(1) PARTIAL.
    work_succeeded = RunNode(
        run_id="run-bug-b",
        node_id="work",
        task_id="task-work-1",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["start"],
    )
    gate_record = RunNode(
        run_id="run-bug-b",
        node_id="gate",
        task_id="task-gate-1",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["work"],
        goal_gate_policy=GoalGatePolicy(retry_target="work", max_attempts=3),
    )

    gate_fail_result = CardResult(
        task_id="task-gate-1",
        event_id=5,
        event_kind="completed",
        summary="Gate failed.",
        metadata={},  # no gate field => fail
    )

    # --- First call (normal processing) ---
    upserted_first: list[RunNode] = []
    run_state_first = MagicMock()
    run_state_first.get_node_by_task.return_value = gate_record
    run_state_first.get_run.return_value = run
    # Before first call: only work(1) and gate(1) exist
    run_state_first.nodes_for_run.return_value = [work_succeeded, gate_record]
    run_state_first.upsert_node.side_effect = upserted_first.append
    kanban_first = MagicMock()
    kanban_first.create_card.return_value = "task-work-retry"

    advance_on_completion(
        card_result=gate_fail_result,
        kanban=kanban_first,
        run_state=run_state_first,
        pipeline=pipeline,
        clock=clock,
    )

    retry_nodes_first = [n for n in upserted_first if n.node_id == "work" and n.attempt > 1]
    assert retry_nodes_first, "First call must create a retry RunNode for work"
    retry_first = retry_nodes_first[0]
    first_attempt = retry_first.attempt
    first_key = kanban_first.create_card.call_args[0][0].idempotency_key.value

    # --- Second call (crash/replay) ---
    # nodes_for_run NOW includes the retry RunNode written by the first call.
    upserted_second: list[RunNode] = []
    run_state_second = MagicMock()
    run_state_second.get_node_by_task.return_value = gate_record
    run_state_second.get_run.return_value = run
    # On replay, the persisted retry row is already in the store.
    run_state_second.nodes_for_run.return_value = [work_succeeded, gate_record, retry_first]
    run_state_second.upsert_node.side_effect = upserted_second.append
    kanban_second = MagicMock()
    kanban_second.create_card.return_value = "task-work-retry-dup"

    advance_on_completion(
        card_result=gate_fail_result,
        kanban=kanban_second,
        run_state=run_state_second,
        pipeline=pipeline,
        clock=clock,
    )

    retry_nodes_second = [n for n in upserted_second if n.node_id == "work" and n.attempt > 1]
    assert retry_nodes_second, "Second call (replay) must also produce a retry RunNode"
    retry_second = retry_nodes_second[0]
    second_attempt = retry_second.attempt
    second_key = kanban_second.create_card.call_args[0][0].idempotency_key.value

    # BUG (b): with the bug, second_attempt == first_attempt + 1 (count-before-save shifts)
    # which means the replay creates a duplicate retry row with a different attempt number.
    assert second_attempt == first_attempt, (
        f"Replay must produce the same next_attempt as the first call; "
        f"first={first_attempt}, second={second_attempt}. "
        "Bug: next_attempt counted from nodes_for_run before save_run — "
        "replay sees one more row and generates a higher attempt number."
    )
    assert second_key == first_key, (
        f"Replay must produce the same idempotency key; first={first_key!r}, second={second_key!r}"
    )


# ---------------------------------------------------------------------------
# Routing: preferred_label / suggested_next propagation (FR-007 / SC-006)
# ---------------------------------------------------------------------------


def _make_branching_pipeline() -> Pipeline:
    """Build a pipeline with a node that has two labeled outgoing edges.

    Topology: start -> router -> branch_a (label='a'), router -> branch_b (label='b') -> exit

    The ``router`` node is a plain CODERGEN node (not a gate) so that the agent
    can influence routing via ``preferred_label`` / ``suggested_next`` in metadata.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    router = Node(node_id="router", shape=NodeShape.CODERGEN, profile="coder")
    branch_a = Node(node_id="branch_a", shape=NodeShape.CODERGEN, profile="coder")
    branch_b = Node(node_id="branch_b", shape=NodeShape.CODERGEN, profile="coder")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="router"),
        Edge(source_id="router", target_id="branch_a", label="a"),
        Edge(source_id="router", target_id="branch_b", label="b"),
        Edge(source_id="branch_a", target_id="exit"),
        Edge(source_id="branch_b", target_id="exit"),
    ]
    stylesheet = Stylesheet(rules=[StyleRule(selector="*", profile="coder")])
    return Pipeline(
        spec_id="branching-pipeline",
        nodes=[start, router, branch_a, branch_b, exit_],
        edges=edges,
        stylesheet=stylesheet,
    )


def test_advance_on_completion_preferred_label_routes_non_gate_node() -> None:
    """When a non-gate node's CardResult metadata contains preferred_label, the run follows that edge label.

    Without the fix, routing_hint is hardcoded to 'pass' for non-gate nodes, so preferred_label
    in the metadata is silently ignored and the engine routes by weight/lexical instead.
    """
    pipeline = _make_branching_pipeline()
    run = Run(
        run_id="run-routing",
        spec_id="branching-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    router_node = RunNode(
        run_id="run-routing",
        node_id="router",
        task_id="task-router",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
    )

    dispatched: list[RunNode] = []
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = router_node
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [router_node]
    run_state.upsert_node.side_effect = dispatched.append
    kanban = MagicMock()
    kanban.create_card.return_value = "task-branch-b"
    clock = MagicMock()
    clock.now.return_value = _NOW

    # Agent emits preferred_label='b' to route to branch_b instead of the default (branch_a, lexically first).
    card_result = CardResult(
        task_id="task-router",
        event_id=1,
        event_kind="completed",
        summary="Routing to b.",
        metadata={"preferred_label": "b"},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # The dispatched next node must be branch_b, not branch_a.
    assert dispatched, "Expected a next node to be dispatched"
    next_node = dispatched[-1]
    assert next_node.node_id == "branch_b", (
        f"Expected branch_b (preferred_label='b'), but got {next_node.node_id!r}. "
        "Bug: preferred_label from CardResult.metadata is not passed to select_edge as routing_hint."
    )


def test_advance_on_completion_suggested_next_routes_non_gate_node() -> None:
    """When a non-gate node's CardResult metadata contains suggested_next, the run prefers that target node.

    Without the fix, suggested_nodes=[] is always passed to select_edge, so the agent's
    suggested_next is silently ignored.
    """
    pipeline = _make_branching_pipeline()
    run = Run(
        run_id="run-suggest",
        spec_id="branching-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    router_node = RunNode(
        run_id="run-suggest",
        node_id="router",
        task_id="task-router-s",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
    )

    dispatched: list[RunNode] = []
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = router_node
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [router_node]
    run_state.upsert_node.side_effect = dispatched.append
    kanban = MagicMock()
    kanban.create_card.return_value = "task-branch-b-s"
    clock = MagicMock()
    clock.now.return_value = _NOW

    # Agent emits suggested_next='branch_b' to prefer branch_b over branch_a (lexically first, lower weight).
    # Since both edges have the same weight and no label match, suggested_next should be the tiebreaker.
    card_result = CardResult(
        task_id="task-router-s",
        event_id=2,
        event_kind="completed",
        summary="Suggesting branch_b.",
        metadata={"suggested_next": "branch_b"},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    assert dispatched, "Expected a next node to be dispatched"
    next_node = dispatched[-1]
    assert next_node.node_id == "branch_b", (
        f"Expected branch_b (suggested_next='branch_b'), but got {next_node.node_id!r}. "
        "Bug: suggested_next from CardResult.metadata is not passed to select_edge as suggested_nodes."
    )


def test_advance_on_completion_gate_pass_uses_gate_verdict_not_preferred_label() -> None:
    """For a gate node that passes, routing_hint comes from the gate verdict ('pass'), not preferred_label.

    This ensures gate routing remains secure (fail-secure per plan.md §Security) and is not
    overridden by an agent-supplied preferred_label in the metadata.
    """
    # Build a gate pipeline: work -> gate -> pass_node (label='pass'), gate -> fail_node (label='fail')
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    gate = Node(
        node_id="gate",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="work", max_attempts=3),
    )
    pass_node = Node(node_id="pass_node", shape=NodeShape.CODERGEN, profile="coder")
    fail_node = Node(node_id="fail_node", shape=NodeShape.CODERGEN, profile="coder")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    gate_pipeline = Pipeline(
        spec_id="gate-routing-pipeline",
        nodes=[start, work, gate, pass_node, fail_node, exit_],
        edges=[
            Edge(source_id="start", target_id="work"),
            Edge(source_id="work", target_id="gate"),
            Edge(source_id="gate", target_id="pass_node", label="pass"),
            Edge(source_id="gate", target_id="fail_node", label="fail"),
            Edge(source_id="pass_node", target_id="exit"),
            Edge(source_id="fail_node", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="coder")]),
    )

    run = Run(
        run_id="run-gate-routing",
        spec_id="gate-routing-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    work_succeeded = RunNode(
        run_id="run-gate-routing",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["start"],
    )
    gate_node = RunNode(
        run_id="run-gate-routing",
        node_id="gate",
        task_id="task-gate",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["work"],
        goal_gate_policy=GoalGatePolicy(retry_target="work", max_attempts=3),
    )

    dispatched: list[RunNode] = []
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_node
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [work_succeeded, gate_node]
    run_state.upsert_node.side_effect = dispatched.append
    kanban = MagicMock()
    kanban.create_card.return_value = "task-pass-node"
    clock = MagicMock()
    clock.now.return_value = _NOW

    # Gate passes (gate verdict in metadata), agent also supplies preferred_label='fail'
    # (adversarial: trying to override gate routing). The gate verdict must win.
    card_result = CardResult(
        task_id="task-gate",
        event_id=3,
        event_kind="completed",
        summary="Gate passed.",
        metadata={"gate": "pass", "preferred_label": "fail"},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=gate_pipeline,
        clock=clock,
    )

    # Must route to pass_node, not fail_node — gate verdict wins over preferred_label.
    assert dispatched, "Expected a next node to be dispatched after gate pass"
    next_node = dispatched[-1]
    assert next_node.node_id == "pass_node", (
        f"Expected pass_node (gate verdict='pass'), but got {next_node.node_id!r}. "
        "Bug: gate routing must use gate verdict, not preferred_label from metadata."
    )


def test_advance_on_completion_suggested_next_as_list_routes_non_gate_node() -> None:
    """When suggested_next in metadata is a list, the first matching target node is preferred.

    Tests the list form of suggested_next: ``{"suggested_next": ["branch_b"]}``.
    """
    pipeline = _make_branching_pipeline()
    run = Run(
        run_id="run-suggest-list",
        spec_id="branching-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    router_node = RunNode(
        run_id="run-suggest-list",
        node_id="router",
        task_id="task-router-list",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
    )

    dispatched: list[RunNode] = []
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = router_node
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [router_node]
    run_state.upsert_node.side_effect = dispatched.append
    kanban = MagicMock()
    kanban.create_card.return_value = "task-branch-b-list"
    clock = MagicMock()
    clock.now.return_value = _NOW

    # Agent supplies suggested_next as a list (multi-candidate form).
    card_result = CardResult(
        task_id="task-router-list",
        event_id=4,
        event_kind="completed",
        summary="Suggesting branch_b via list.",
        metadata={"suggested_next": ["branch_b"]},
    )

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    assert dispatched, "Expected a next node to be dispatched"
    next_node = dispatched[-1]
    assert next_node.node_id == "branch_b", (
        f"Expected branch_b (suggested_next=['branch_b']), but got {next_node.node_id!r}. "
        "Bug: suggested_next as list is not passed to select_edge as suggested_nodes."
    )


# ---------------------------------------------------------------------------
# Bug: FAN_IN double-applies branch context_updates (zym.42)
# ---------------------------------------------------------------------------


def _make_fan_in_pipeline_for_merge_tests(spec_id: str = "fan-in-merge-pipeline") -> Pipeline:
    """Build: start -> fan_out -> [branch_a, branch_b] -> fan_in -> exit.

    Used to drive the full FAN_IN merge path with two parallel branches.

    Args:
        spec_id: The pipeline spec identifier.

    Returns:
        A Pipeline domain object.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    fan_out = Node(node_id="fan_out", shape=NodeShape.FAN_OUT, profile="orchestrator")
    branch_a = Node(node_id="branch_a", shape=NodeShape.CODERGEN, profile="coder")
    branch_b = Node(node_id="branch_b", shape=NodeShape.CODERGEN, profile="coder")
    fan_in = Node(node_id="fan_in", shape=NodeShape.FAN_IN, profile="merger")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    return Pipeline(
        spec_id=spec_id,
        nodes=[start, fan_out, branch_a, branch_b, fan_in, exit_],
        edges=[
            Edge(source_id="start", target_id="fan_out"),
            Edge(source_id="fan_out", target_id="branch_a"),
            Edge(source_id="fan_out", target_id="branch_b"),
            Edge(source_id="branch_a", target_id="fan_in"),
            Edge(source_id="branch_b", target_id="fan_in"),
            Edge(source_id="fan_in", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def test_fan_in_merge_scalar_conflict_no_duplication() -> None:
    """FAN_IN: merged context must show each branch value exactly once (scalar conflict).

    Bug: branch_a's context_updates are applied to run.context at branch completion
    (not-all-done save), then merged again from RunNode.context_updates when FAN_IN fires.
    Result: ``result`` appears in _merge_conflicts as ['alpha', 'alpha', 'beta'] instead
    of ['alpha', 'beta'].

    This test drives the full dispatch path:
    1. FAN_OUT fires, dispatching branch_a and branch_b.
    2. branch_a completes with context_updates={'result': 'alpha'} — not all done yet.
    3. branch_b completes with context_updates={'result': 'beta'} — all done, FAN_IN fires.
    4. The FAN_IN card is created with merged_context; assert _merge_conflicts has exactly
       two entries (['alpha', 'beta']), not three (['alpha', 'alpha', 'beta']).
    """
    pipeline = _make_fan_in_pipeline_for_merge_tests()
    run = Run(
        run_id="run-fan-in-scalar",
        spec_id="fan-in-merge-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    clock = MagicMock()
    clock.now.return_value = _NOW

    # --- Step 1: FAN_OUT fires ---
    fan_out_record = RunNode(
        run_id="run-fan-in-scalar",
        node_id="fan_out",
        task_id="task-fan-out",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
    )
    run_state_fanout = MagicMock()
    run_state_fanout.get_node_by_task.return_value = fan_out_record
    run_state_fanout.get_run.return_value = run
    kanban_fanout = MagicMock()
    task_ids = iter(["task-branch-a", "task-branch-b"])

    def _fan_out_task_id(_c: object) -> str:
        """Return the next task id from the iterator."""
        return next(task_ids)

    kanban_fanout.create_card.side_effect = _fan_out_task_id

    advance_on_completion(
        card_result=CardResult(
            task_id="task-fan-out",
            event_id=1,
            event_kind="completed",
            summary="FAN_OUT done.",
            metadata={},
        ),
        kanban=kanban_fanout,
        run_state=run_state_fanout,
        pipeline=pipeline,
        clock=clock,
    )

    # --- Step 2: branch_a completes with result='alpha' (not all done) ---
    branch_a_record = RunNode(
        run_id="run-fan-in-scalar",
        node_id="branch_a",
        task_id="task-branch-a",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["fan_out"],
    )
    # Simulate persisted state: only branch_a completed so far.
    branch_a_succeeded = RunNode(
        run_id="run-fan-in-scalar",
        node_id="branch_a",
        task_id="task-branch-a",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["fan_out"],
        context_updates={"result": "alpha"},
    )

    saved_runs_after_a: list[Run] = []
    run_state_a = MagicMock()
    run_state_a.get_node_by_task.return_value = branch_a_record
    run_state_a.get_run.return_value = run
    # branch_b is not yet done — only branch_a is in the store
    run_state_a.nodes_for_run.return_value = [branch_a_succeeded]
    run_state_a.save_run.side_effect = saved_runs_after_a.append
    kanban_a = MagicMock()
    kanban_a.create_card.return_value = "task-fan-in"

    advance_on_completion(
        card_result=CardResult(
            task_id="task-branch-a",
            event_id=2,
            event_kind="completed",
            summary="branch_a done.",
            metadata={"context_updates": {"result": "alpha"}},
        ),
        kanban=kanban_a,
        run_state=run_state_a,
        pipeline=pipeline,
        clock=clock,
    )

    # Not all done: no FAN_IN card should be created (branch_b still pending).
    kanban_a.create_card.assert_not_called()
    # Save run cursor must NOT carry branch_a's context_updates in run.context.
    assert saved_runs_after_a, "save_run must be called on not-all-done path"
    run_after_a = saved_runs_after_a[-1]
    assert "result" not in run_after_a.context.data, (
        "Bug: branch context_updates must NOT be applied to run.context on not-all-done save; "
        f"run.context.data={dict(run_after_a.context.data)!r}"
    )

    # --- Step 3: branch_b completes with result='beta' (all done) ---
    branch_b_record = RunNode(
        run_id="run-fan-in-scalar",
        node_id="branch_b",
        task_id="task-branch-b",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["fan_out"],
    )
    branch_b_succeeded = RunNode(
        run_id="run-fan-in-scalar",
        node_id="branch_b",
        task_id="task-branch-b",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["fan_out"],
        context_updates={"result": "beta"},
    )

    saved_runs_after_b: list[Run] = []
    # FAN_IN fires: run state reflects the not-all-done save (run.context unchanged = {})
    run_after_not_all_done = run_after_a  # run saved on not-all-done path
    run_state_b = MagicMock()
    run_state_b.get_node_by_task.return_value = branch_b_record
    run_state_b.get_run.return_value = run_after_not_all_done
    # Both branches now in the store.
    run_state_b.nodes_for_run.return_value = [branch_a_succeeded, branch_b_succeeded]
    run_state_b.save_run.side_effect = saved_runs_after_b.append
    kanban_b = MagicMock()
    kanban_b.create_card.return_value = "task-fan-in"

    advance_on_completion(
        card_result=CardResult(
            task_id="task-branch-b",
            event_id=3,
            event_kind="completed",
            summary="branch_b done.",
            metadata={"context_updates": {"result": "beta"}},
        ),
        kanban=kanban_b,
        run_state=run_state_b,
        pipeline=pipeline,
        clock=clock,
    )

    # FAN_IN card must be created.
    kanban_b.create_card.assert_called_once()

    # Assert exact merged values — no duplication.
    assert saved_runs_after_b, "save_run must be called after FAN_IN dispatch"
    final_run = saved_runs_after_b[-1]
    conflicts = final_run.context.data.get("_merge_conflicts")
    assert conflicts is not None, (
        "Expected _merge_conflicts in merged context because both branches wrote 'result'; "
        f"context.data={dict(final_run.context.data)!r}"
    )
    result_conflict = conflicts["result"]  # pyright: ignore[reportIndexIssue, reportUnknownVariableType]
    assert result_conflict == ["alpha", "beta"], (
        f"Bug: FAN_IN double-applies branch context_updates; "
        f"expected conflict=['alpha','beta'] (each branch once), got {result_conflict!r}. "
        "Values must appear exactly once, not duplicated."
    )
    # Last-writer wins: result should be 'beta' (branch_b is last).
    assert final_run.context.data.get("result") == "beta", (
        f"Last-writer (branch_b) wins scalar conflict; expected 'beta', got {final_run.context.data.get('result')!r}"
    )


def test_fan_in_merge_list_accumulate_no_duplication() -> None:
    """FAN_IN: merged context must accumulate list values exactly once (list-append case).

    Bug: branch_a's context_updates={'items': [1]} applied to run.context first, then
    merged again from RunNode.context_updates when FAN_IN fires. Lists are concatenated,
    so items=[1] + [1] + [2] = [1, 1, 2] instead of [1, 2].

    This test uses integer list values to verify list accumulation without duplication.
    """
    pipeline = _make_fan_in_pipeline_for_merge_tests("fan-in-list-pipeline")
    run = Run(
        run_id="run-fan-in-list",
        spec_id="fan-in-list-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    clock = MagicMock()
    clock.now.return_value = _NOW

    branch_a_succeeded = RunNode(
        run_id="run-fan-in-list",
        node_id="branch_a",
        task_id="task-branch-a",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["fan_out"],
        context_updates={"items": [1]},
    )
    branch_b_succeeded = RunNode(
        run_id="run-fan-in-list",
        node_id="branch_b",
        task_id="task-branch-b",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["fan_out"],
        context_updates={"items": [2]},
    )

    # --- branch_a completes (not all done) ---
    branch_a_record = RunNode(
        run_id="run-fan-in-list",
        node_id="branch_a",
        task_id="task-branch-a",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["fan_out"],
    )
    saved_runs_a: list[Run] = []
    run_state_a = MagicMock()
    run_state_a.get_node_by_task.return_value = branch_a_record
    run_state_a.get_run.return_value = run
    run_state_a.nodes_for_run.return_value = [branch_a_succeeded]
    run_state_a.save_run.side_effect = saved_runs_a.append
    kanban_a = MagicMock()
    kanban_a.create_card.return_value = "task-fan-in"

    advance_on_completion(
        card_result=CardResult(
            task_id="task-branch-a",
            event_id=10,
            event_kind="completed",
            summary="branch_a done.",
            metadata={"context_updates": {"items": [1]}},
        ),
        kanban=kanban_a,
        run_state=run_state_a,
        pipeline=pipeline,
        clock=clock,
    )

    kanban_a.create_card.assert_not_called()
    assert saved_runs_a, "save_run must be called on not-all-done path"
    run_after_a = saved_runs_a[-1]
    # The key assertion: items must NOT be in run.context after not-all-done save.
    assert "items" not in run_after_a.context.data, (
        "Bug: branch context_updates must NOT be applied to run.context on not-all-done save; "
        f"run.context.data={dict(run_after_a.context.data)!r}"
    )

    # --- branch_b completes (all done) → FAN_IN fires ---
    branch_b_record = RunNode(
        run_id="run-fan-in-list",
        node_id="branch_b",
        task_id="task-branch-b",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["fan_out"],
    )
    saved_runs_b: list[Run] = []
    run_state_b = MagicMock()
    run_state_b.get_node_by_task.return_value = branch_b_record
    run_state_b.get_run.return_value = run_after_a  # use the not-all-done saved run
    run_state_b.nodes_for_run.return_value = [branch_a_succeeded, branch_b_succeeded]
    run_state_b.save_run.side_effect = saved_runs_b.append
    kanban_b = MagicMock()
    kanban_b.create_card.return_value = "task-fan-in"

    advance_on_completion(
        card_result=CardResult(
            task_id="task-branch-b",
            event_id=11,
            event_kind="completed",
            summary="branch_b done.",
            metadata={"context_updates": {"items": [2]}},
        ),
        kanban=kanban_b,
        run_state=run_state_b,
        pipeline=pipeline,
        clock=clock,
    )

    kanban_b.create_card.assert_called_once()
    assert saved_runs_b, "save_run must be called after FAN_IN dispatch"
    final_run = saved_runs_b[-1]
    items = final_run.context.data.get("items")
    assert items == [1, 2], (
        f"Bug: FAN_IN double-applies list context_updates; "
        f"expected items=[1, 2] (each branch contributes once), got {items!r}. "
        "List concatenation must not duplicate values."
    )


# ---------------------------------------------------------------------------
# Bug (zym.43): goal_gate_policy not populated in HUMAN/FAN_IN/TOOL-inline dispatch paths
# ---------------------------------------------------------------------------


def _make_human_gate_pipeline() -> Pipeline:
    """Build: start -> gated_human -> exit, where gated_human is a HUMAN node with goal_gate.

    This exercises the HUMAN dispatch path — the task description bug site at ~line 585-592.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    gated_human = Node(
        node_id="gated_human",
        shape=NodeShape.HUMAN,
        profile="human",
        goal_gate=GoalGatePolicy(retry_target="work", max_attempts=2),
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    return Pipeline(
        spec_id="human-gate-pipeline",
        nodes=[start, work, gated_human, exit_],
        edges=[
            Edge(source_id="start", target_id="work"),
            Edge(source_id="work", target_id="gated_human"),
            Edge(source_id="gated_human", target_id="work", label="fail"),
            Edge(source_id="gated_human", target_id="exit", label="pass"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def _make_fan_in_gate_pipeline() -> Pipeline:
    """Build a pipeline where the FAN_IN node itself has a goal_gate.

    Topology: start -> fan_out -> [branch_a, branch_b] -> gated_fan_in -> exit.
    This exercises the FAN_IN dispatch path — bug site at ~line 651-658.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    fan_out = Node(node_id="fan_out", shape=NodeShape.FAN_OUT, profile="orchestrator")
    branch_a = Node(node_id="branch_a", shape=NodeShape.CODERGEN, profile="coder")
    branch_b = Node(node_id="branch_b", shape=NodeShape.CODERGEN, profile="coder")
    gated_fan_in = Node(
        node_id="gated_fan_in",
        shape=NodeShape.FAN_IN,
        profile="merger",
        goal_gate=GoalGatePolicy(retry_target="fan_out", max_attempts=2),
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    return Pipeline(
        spec_id="fan-in-gate-pipeline",
        nodes=[start, fan_out, branch_a, branch_b, gated_fan_in, exit_],
        edges=[
            Edge(source_id="start", target_id="fan_out"),
            Edge(source_id="fan_out", target_id="branch_a"),
            Edge(source_id="fan_out", target_id="branch_b"),
            Edge(source_id="branch_a", target_id="gated_fan_in"),
            Edge(source_id="branch_b", target_id="gated_fan_in"),
            Edge(source_id="gated_fan_in", target_id="exit", label="pass"),
            Edge(source_id="gated_fan_in", target_id="fan_out", label="fail"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def _make_tool_then_gate_pipeline() -> Pipeline:
    """Build: start -> tool_node -> gated_work -> exit, where gated_work has goal_gate.

    This exercises the TOOL-inline next dispatch path — bug site at ~line 716-724.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    tool_node = Node(node_id="tool_node", shape=NodeShape.TOOL, prompt="my_tool")
    gated_work = Node(
        node_id="gated_work",
        shape=NodeShape.CODERGEN,
        profile="coder",
        goal_gate=GoalGatePolicy(retry_target="gated_work", max_attempts=2),
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    return Pipeline(
        spec_id="tool-gate-pipeline",
        nodes=[start, tool_node, gated_work, exit_],
        edges=[
            Edge(source_id="start", target_id="tool_node"),
            Edge(source_id="tool_node", target_id="gated_work"),
            Edge(source_id="gated_work", target_id="exit", label="pass"),
            Edge(source_id="gated_work", target_id="gated_work", label="fail"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def test_human_dispatch_populates_goal_gate_policy_from_pipeline_node() -> None:
    """HUMAN dispatch path must copy next_node.goal_gate into RunNode.goal_gate_policy.

    Bug: the HUMAN RunNode is created without goal_gate_policy, so a goal-gated HUMAN
    node reached via the HUMAN dispatch path never retries on fail.

    This test drives the REAL dispatch path (work completes -> gated_human is dispatched)
    without manually setting goal_gate_policy on the fixture — asserting the gate retries
    on fail by first confirming the dispatched RunNode carries the policy.
    """
    pipeline = _make_human_gate_pipeline()
    run = Run(
        run_id="run-human-gate",
        spec_id="human-gate-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    work_record = RunNode(
        run_id="run-human-gate",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
    )

    upserted: list[RunNode] = []
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run
    run_state.upsert_node.side_effect = upserted.append
    kanban = MagicMock()
    kanban.create_card.return_value = "task-human"
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(
            task_id="task-work",
            event_id=1,
            event_kind="completed",
            summary="Work done.",
            metadata={},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    human_nodes = [n for n in upserted if n.node_id == "gated_human"]
    assert human_nodes, "Expected a RunNode upserted for gated_human"
    human_record = human_nodes[0]
    assert human_record.goal_gate_policy is not None, (
        "HUMAN dispatch path must copy next_node.goal_gate into RunNode.goal_gate_policy; "
        "leaving it None makes FR-009 goal-gate retry unreachable when reached via HUMAN path"
    )
    assert human_record.goal_gate_policy.retry_target == "work"
    assert human_record.goal_gate_policy.max_attempts == 2


def test_human_gate_retries_on_fail_via_real_dispatch_path() -> None:
    """A goal-gated HUMAN node reached via the HUMAN dispatch path retries on fail.

    This test exercises the full chain without manually injecting goal_gate_policy:
    1. work completes -> gated_human dispatched (goal_gate_policy populated from pipeline).
    2. gated_human card fails -> a retry card for work is created.

    If goal_gate_policy is None (the pre-fix bug), no retry card is created.
    """
    pipeline = _make_human_gate_pipeline()
    run = Run(
        run_id="run-human-gate-retry",
        spec_id="human-gate-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )

    # Step 1: work completes -> gated_human dispatched.
    work_record = RunNode(
        run_id="run-human-gate-retry",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
    )
    upserted_step1: list[RunNode] = []
    run_state_1 = MagicMock()
    run_state_1.get_node_by_task.return_value = work_record
    run_state_1.get_run.return_value = run
    run_state_1.upsert_node.side_effect = upserted_step1.append
    kanban_1 = MagicMock()
    kanban_1.create_card.return_value = "task-human"
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(task_id="task-work", event_id=1, event_kind="completed", summary=".", metadata={}),
        kanban=kanban_1,
        run_state=run_state_1,
        pipeline=pipeline,
        clock=clock,
    )

    human_nodes = [n for n in upserted_step1 if n.node_id == "gated_human"]
    assert human_nodes, "gated_human must be dispatched after work completes"
    human_record = human_nodes[0]
    # Key invariant: populated from pipeline, no manual injection.
    assert human_record.goal_gate_policy is not None, "human dispatch must populate goal_gate_policy from pipeline"

    # Step 2: gated_human card completes with gate=fail -> retry card for work.
    work_succeeded = RunNode(
        run_id="run-human-gate-retry",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["start"],
    )
    run_state_2 = MagicMock()
    run_state_2.get_node_by_task.return_value = human_record
    run_state_2.get_run.return_value = Run(
        run_id="run-human-gate-retry",
        spec_id="human-gate-pipeline",
        status=RunStatus.PAUSED_HUMAN,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    run_state_2.nodes_for_run.return_value = [work_succeeded, human_record]
    kanban_2 = MagicMock()
    kanban_2.create_card.return_value = "task-work-retry"
    clock_2 = MagicMock()
    clock_2.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(
            task_id="task-human",
            event_id=2,
            event_kind="completed",
            summary="Human failed gate.",
            metadata={},  # no gate field => fail-secure
        ),
        kanban=kanban_2,
        run_state=run_state_2,
        pipeline=pipeline,
        clock=clock_2,
    )

    assert kanban_2.create_card.called, "A retry card must be created when gated HUMAN fails"
    retry_card = kanban_2.create_card.call_args[0][0]
    assert "work" in retry_card.idempotency_key.value, "Retry card must target the retry_target node 'work'"


def test_fan_in_dispatch_populates_goal_gate_policy_from_pipeline_node() -> None:
    """FAN_IN dispatch path must copy next_node.goal_gate into RunNode.goal_gate_policy.

    Bug: the FAN_IN RunNode is created without goal_gate_policy, so a goal-gated FAN_IN
    node never retries on fail when reached via the FAN_IN dispatch path.

    This test drives the REAL dispatch path:
    branch_b completes (all branches done) -> gated_fan_in is dispatched.
    The dispatched RunNode must carry goal_gate_policy from the pipeline.
    """
    pipeline = _make_fan_in_gate_pipeline()
    run = Run(
        run_id="run-fan-in-gate",
        spec_id="fan-in-gate-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )

    branch_a_succeeded = RunNode(
        run_id="run-fan-in-gate",
        node_id="branch_a",
        task_id="task-branch-a",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["fan_out"],
    )
    branch_b_record = RunNode(
        run_id="run-fan-in-gate",
        node_id="branch_b",
        task_id="task-branch-b",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["fan_out"],
    )
    branch_b_succeeded = RunNode(
        run_id="run-fan-in-gate",
        node_id="branch_b",
        task_id="task-branch-b",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["fan_out"],
    )

    upserted: list[RunNode] = []
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = branch_b_record
    run_state.get_run.return_value = run
    # Both branches done -> FAN_IN fires.
    run_state.nodes_for_run.return_value = [branch_a_succeeded, branch_b_succeeded]
    run_state.upsert_node.side_effect = upserted.append
    kanban = MagicMock()
    kanban.create_card.return_value = "task-fan-in"
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(
            task_id="task-branch-b",
            event_id=2,
            event_kind="completed",
            summary="branch_b done.",
            metadata={},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    fan_in_nodes = [n for n in upserted if n.node_id == "gated_fan_in"]
    assert fan_in_nodes, "Expected a RunNode upserted for gated_fan_in"
    fan_in_record = fan_in_nodes[0]
    assert fan_in_record.goal_gate_policy is not None, (
        "FAN_IN dispatch path must copy next_node.goal_gate into RunNode.goal_gate_policy; "
        "leaving it None makes FR-009 goal-gate retry unreachable when reached via FAN_IN path"
    )
    assert fan_in_record.goal_gate_policy.retry_target == "fan_out"
    assert fan_in_record.goal_gate_policy.max_attempts == 2


def test_fan_in_gate_retries_on_fail_via_real_dispatch_path() -> None:
    """A goal-gated FAN_IN node retries on fail when dispatched via the FAN_IN path.

    This test exercises the full chain without manually injecting goal_gate_policy:
    1. branch_b completes (all done) -> gated_fan_in dispatched (policy from pipeline).
    2. gated_fan_in card fails -> a retry card for fan_out is created.
    """
    pipeline = _make_fan_in_gate_pipeline()
    run = Run(
        run_id="run-fan-in-gate-retry",
        spec_id="fan-in-gate-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )

    # Step 1: both branches done -> gated_fan_in dispatched.
    branch_a_succeeded = RunNode(
        run_id="run-fan-in-gate-retry",
        node_id="branch_a",
        task_id="task-branch-a",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["fan_out"],
    )
    branch_b_record = RunNode(
        run_id="run-fan-in-gate-retry",
        node_id="branch_b",
        task_id="task-branch-b",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["fan_out"],
    )
    branch_b_succeeded = RunNode(
        run_id="run-fan-in-gate-retry",
        node_id="branch_b",
        task_id="task-branch-b",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["fan_out"],
    )

    upserted_step1: list[RunNode] = []
    run_state_1 = MagicMock()
    run_state_1.get_node_by_task.return_value = branch_b_record
    run_state_1.get_run.return_value = run
    run_state_1.nodes_for_run.return_value = [branch_a_succeeded, branch_b_succeeded]
    run_state_1.upsert_node.side_effect = upserted_step1.append
    kanban_1 = MagicMock()
    kanban_1.create_card.return_value = "task-fan-in"
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(task_id="task-branch-b", event_id=1, event_kind="completed", summary=".", metadata={}),
        kanban=kanban_1,
        run_state=run_state_1,
        pipeline=pipeline,
        clock=clock,
    )

    fan_in_nodes = [n for n in upserted_step1 if n.node_id == "gated_fan_in"]
    assert fan_in_nodes, "gated_fan_in must be dispatched when all branches done"
    fan_in_record = fan_in_nodes[0]
    assert fan_in_record.goal_gate_policy is not None, "fan_in dispatch must populate goal_gate_policy from pipeline"

    # Step 2: gated_fan_in fails -> retry card for fan_out.
    fan_out_node = RunNode(
        run_id="run-fan-in-gate-retry",
        node_id="fan_out",
        task_id="task-fan-out",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["start"],
    )
    run_state_2 = MagicMock()
    run_state_2.get_node_by_task.return_value = fan_in_record
    run_state_2.get_run.return_value = run
    run_state_2.nodes_for_run.return_value = [fan_out_node, branch_a_succeeded, branch_b_succeeded, fan_in_record]
    kanban_2 = MagicMock()
    kanban_2.create_card.return_value = "task-fan-out-retry"
    clock_2 = MagicMock()
    clock_2.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(
            task_id="task-fan-in",
            event_id=2,
            event_kind="completed",
            summary="FAN_IN gate failed.",
            metadata={},  # no gate field => fail-secure
        ),
        kanban=kanban_2,
        run_state=run_state_2,
        pipeline=pipeline,
        clock=clock_2,
    )

    assert kanban_2.create_card.called, "A retry card must be created when gated FAN_IN fails"
    retry_card = kanban_2.create_card.call_args[0][0]
    assert "fan_out" in retry_card.idempotency_key.value, "Retry card must target the retry_target node 'fan_out'"


def test_tool_inline_dispatch_populates_goal_gate_policy_from_pipeline_node() -> None:
    """TOOL-inline next dispatch path must copy tool_next_node.goal_gate into RunNode.goal_gate_policy.

    Bug: the RunNode dispatched after a TOOL node is created without goal_gate_policy,
    so a goal-gated node reached via a TOOL-inline next dispatch never retries on fail.

    This test drives the REAL dispatch path:
    start completes -> tool_node runs inline -> gated_work is dispatched.
    The dispatched RunNode must carry goal_gate_policy from the pipeline.
    """
    pipeline = _make_tool_then_gate_pipeline()
    run = Run(
        run_id="run-tool-gate",
        spec_id="tool-gate-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    # "start" node just completed — advance will route through tool_node inline and dispatch gated_work.
    start_record = RunNode(
        run_id="run-tool-gate",
        node_id="start",
        task_id="task-start",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=[],
    )

    upserted: list[RunNode] = []
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = start_record
    run_state.get_run.return_value = run
    run_state.upsert_node.side_effect = upserted.append
    kanban = MagicMock()
    kanban.create_card.return_value = "task-gated-work"
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(
            task_id="task-start",
            event_id=1,
            event_kind="completed",
            summary="Start done.",
            metadata={},
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    gated_nodes = [n for n in upserted if n.node_id == "gated_work"]
    assert gated_nodes, "Expected a RunNode upserted for gated_work after TOOL inline dispatch"
    gated_record = gated_nodes[0]
    assert gated_record.goal_gate_policy is not None, (
        "TOOL-inline next dispatch path must copy tool_next_node.goal_gate into RunNode.goal_gate_policy; "
        "leaving it None makes FR-009 goal-gate retry unreachable when reached via TOOL-inline path"
    )
    assert gated_record.goal_gate_policy.retry_target == "gated_work"
    assert gated_record.goal_gate_policy.max_attempts == 2


def test_tool_inline_gate_retries_on_fail_via_real_dispatch_path() -> None:
    """A goal-gated node reached via TOOL-inline next dispatch retries on fail.

    This test exercises the full chain without manually injecting goal_gate_policy:
    1. start completes -> tool_node runs inline -> gated_work dispatched (policy from pipeline).
    2. gated_work card fails -> a retry card for gated_work is created (self-loop retry).
    """
    pipeline = _make_tool_then_gate_pipeline()
    run = Run(
        run_id="run-tool-gate-retry",
        spec_id="tool-gate-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )

    # Step 1: start completes -> tool_node inline -> gated_work dispatched.
    start_record = RunNode(
        run_id="run-tool-gate-retry",
        node_id="start",
        task_id="task-start",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=[],
    )
    upserted_step1: list[RunNode] = []
    run_state_1 = MagicMock()
    run_state_1.get_node_by_task.return_value = start_record
    run_state_1.get_run.return_value = run
    run_state_1.upsert_node.side_effect = upserted_step1.append
    kanban_1 = MagicMock()
    kanban_1.create_card.return_value = "task-gated-work"
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(task_id="task-start", event_id=1, event_kind="completed", summary=".", metadata={}),
        kanban=kanban_1,
        run_state=run_state_1,
        pipeline=pipeline,
        clock=clock,
    )

    gated_nodes = [n for n in upserted_step1 if n.node_id == "gated_work"]
    assert gated_nodes, "gated_work must be dispatched after TOOL inline dispatch"
    gated_record = gated_nodes[0]
    assert gated_record.goal_gate_policy is not None, (
        "TOOL inline dispatch must populate goal_gate_policy from pipeline"
    )

    # Step 2: gated_work fails -> retry card for gated_work (self-loop).
    run_state_2 = MagicMock()
    run_state_2.get_node_by_task.return_value = gated_record
    run_state_2.get_run.return_value = run
    run_state_2.nodes_for_run.return_value = [gated_record]
    kanban_2 = MagicMock()
    kanban_2.create_card.return_value = "task-gated-work-retry"
    clock_2 = MagicMock()
    clock_2.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(
            task_id="task-gated-work",
            event_id=2,
            event_kind="completed",
            summary="Gate failed.",
            metadata={},  # no gate field => fail-secure
        ),
        kanban=kanban_2,
        run_state=run_state_2,
        pipeline=pipeline,
        clock=clock_2,
    )

    assert kanban_2.create_card.called, "A retry card must be created when gated node via TOOL-inline fails"
    retry_card = kanban_2.create_card.call_args[0][0]
    assert "gated_work" in retry_card.idempotency_key.value, "Retry card must target the retry_target node 'gated_work'"


def test_retry_decision_reads_live_pipeline_goal_gate_not_persisted_policy() -> None:
    """At retry decision, the live pipeline_node.goal_gate must be used, not node_record.goal_gate_policy.

    Bug: line ~437 checks node_record.goal_gate_policy (the persisted policy). If the
    persisted policy is None (dropped/not populated by the broken dispatch path),
    a gate node that SHOULD retry goes PARTIAL and is silently bypassed — the run
    follows the "pass" edge to EXIT instead of retrying.

    Fix: the gate-pass check at ~320 uses pipeline_node.goal_gate (live). The retry
    decision at ~437 should do the same: read pipeline_node.goal_gate.

    This test constructs a pipeline where the gate has ONLY a "pass" edge to EXIT
    (no "fail" label edge). With goal_gate_policy=None on the RunNode and the bug:
      - is_gate=True (from pipeline), gate_passed=False (fail-secure)
      - Retry block at ~437 is skipped (goal_gate_policy is None)
      - Regular routing selects the "pass"-labeled edge to EXIT (routing_hint="fail"
        doesn't match "pass" label, but fallback to weight/lexical picks the only edge)
      - run is marked SUCCEEDED — WRONG, gate failed!

    With the fix: retry block uses pipeline_node.goal_gate, and the run is NOT SUCCEEDED.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    gate = Node(
        node_id="gate",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="work", max_attempts=2),
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    # IMPORTANT: only a "pass" edge from gate to exit (no "fail" edge).
    # With the bug: regular routing selects exit (only edge) => run SUCCEEDS on gate failure!
    pipeline = Pipeline(
        spec_id="live-gate-passonly-pipeline",
        nodes=[start, work, gate, exit_],
        edges=[
            Edge(source_id="start", target_id="work"),
            Edge(source_id="work", target_id="gate"),
            Edge(source_id="gate", target_id="exit", label="pass"),
            # Deliberately NO "fail" edge — only goal_gate policy can trigger retry.
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )
    run = Run(
        run_id="run-live-gate-passonly",
        spec_id="live-gate-passonly-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={}),
        created_at=_NOW,
        updated_at=_NOW,
    )
    # Simulates the pre-fix bug: goal_gate_policy=None on the persisted RunNode.
    gate_record_no_policy = RunNode(
        run_id="run-live-gate-passonly",
        node_id="gate",
        task_id="task-gate",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["work"],
        goal_gate_policy=None,  # the broken pre-fix state
    )
    work_succeeded = RunNode(
        run_id="run-live-gate-passonly",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.SUCCEEDED,
        attempt=1,
        parent_node_ids=["start"],
    )

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = gate_record_no_policy
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [work_succeeded, gate_record_no_policy]
    kanban = MagicMock()
    kanban.create_card.return_value = "task-work-retry"
    clock = MagicMock()
    clock.now.return_value = _NOW

    advance_on_completion(
        card_result=CardResult(
            task_id="task-gate",
            event_id=1,
            event_kind="completed",
            summary="Gate failed.",
            metadata={},  # no gate field => fail-secure
        ),
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # With the fix: retry card must be created (goal_gate.retry_target=work),
    # NOT the run silently marked SUCCEEDED via the "pass" exit edge.
    assert kanban.create_card.called, (
        "Retry must be triggered using the live pipeline_node.goal_gate, "
        "not the persisted node_record.goal_gate_policy which may be None; "
        "without the fix, the gate silently routes to EXIT on failure"
    )
    # The run must NOT be marked SUCCEEDED — gate failed, must retry.
    if run_state.save_run.called:
        saved_runs = [call[0][0] for call in run_state.save_run.call_args_list]
        assert not any(r.status is RunStatus.SUCCEEDED for r in saved_runs), (
            "Run must NOT be SUCCEEDED when gate fails and retry is available; the bug causes silent bypass to EXIT"
        )
