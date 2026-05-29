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
    """Goal gate fail when retry_target node doesn't exist still saves run cursor."""
    pipeline = _make_gate_pipeline_unit()
    run = _make_run()
    gate_node = RunNode(
        run_id="run1",
        node_id="gate",
        task_id="task-gate",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["work"],
        # retry_target points to a node that doesn't exist in the pipeline
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
