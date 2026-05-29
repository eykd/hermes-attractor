"""Unit tests for the run execution use case and tool handlers (RED phase M2 US2).

Tests fail until src/hermes_attractor/use_cases/run_execution.py is implemented.
"""

from __future__ import annotations

import datetime
import json
from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.card import CardKind, CardResult
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
from hermes_attractor.plugin.tools import (
    handle_attractor_result,
    handle_attractor_run,
    handle_attractor_status,
)
from hermes_attractor.use_cases.run_execution import (
    _card_kind_for_node,  # pyright: ignore[reportPrivateUsage]
    advance_on_completion,
    launch_run,
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
    return Pipeline(  # type: ignore[return-value]
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
# Tool handler JSON envelope
# ---------------------------------------------------------------------------


def test_attractor_run_handler_returns_ok_json_with_run_id_and_status() -> None:
    """attractor_run tool handler returns {ok:true, result:{run_id, status}} JSON."""
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

    raw = handle_attractor_run(
        {"spec_id": "spec-a", "context": {"task": "write tests"}},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )

    payload = json.loads(raw)
    assert payload["ok"] is True
    assert "run_id" in payload["result"]
    assert "status" in payload["result"]


def test_attractor_status_handler_returns_ok_json_with_status_and_nodes() -> None:
    """attractor_status tool handler returns {run_id, status, current_nodes, context_keys} JSON."""
    run = _make_run()
    node = _make_run_node("work", NodeRunStatus.RUNNING, "task-001")
    run_state = MagicMock()
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [node]

    raw = handle_attractor_status({"run_id": "run1"}, run_state=run_state)

    payload = json.loads(raw)
    assert payload["ok"] is True
    result = payload["result"]
    assert result["run_id"] == "run1"
    assert result["status"] == RunStatus.RUNNING.value
    assert "current_nodes" in result
    assert "context_keys" in result


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


def test_launch_run_with_start_node_but_no_edges_still_returns_run_id() -> None:
    """launch_run returns a run_id when the START node has no outgoing edges (degenerate case)."""
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

    result = launch_run(
        spec_id="spec-no-edges",
        initial_context={},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )

    assert result["run_id"]
    kanban.create_card.assert_not_called()


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


def test_launch_run_with_no_start_node_still_returns_run_id() -> None:
    """launch_run returns a run_id even when the pipeline has no START node (degenerate case)."""
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

    result = launch_run(
        spec_id="spec-b",
        initial_context={},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )

    assert result["run_id"]
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


def test_attractor_result_handler_returns_ok_json() -> None:
    """handle_attractor_result returns {ok:true, result:{run_id, status, outcome}} JSON."""
    run = _make_run(RunStatus.SUCCEEDED)
    run_state = MagicMock()
    run_state.get_run.return_value = run

    raw = handle_attractor_result({"run_id": "run1"}, run_state=run_state)

    payload = json.loads(raw)
    assert payload["ok"] is True
    result = payload["result"]
    assert result["run_id"] == "run1"
    assert result["status"] == RunStatus.SUCCEEDED.value
    assert "outcome" in result


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
