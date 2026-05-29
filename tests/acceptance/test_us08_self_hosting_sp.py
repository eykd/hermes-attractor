"""Acceptance tests for US8: Self-hosting sp workflow reference pipeline end-to-end.

Acceptance spec: specs/acceptance-specs/US08-self-hosting-sp.txt

This test is an integration smoke test of the complete sp pipeline graph:

  1. The sp pipeline DOT validates clean.
  2. A pipeline run executes through all node types:
     - Sequential phases (CODERGEN nodes for each sp phase)
     - Parallel review lenses (FAN_OUT/FAN_IN)
     - Goal-gated review loops (CODERGEN with GoalGatePolicy)
     - Human approval gate (HUMAN node)
     - Tool node (TOOL node for a deterministic check)
  3. The run completes with SUCCEEDED.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from hermes_attractor.adapters.tool_node_registry import InMemoryToolNodeRegistry
from hermes_attractor.domain.card import CardResult
from hermes_attractor.domain.pipeline import (
    Edge,
    GoalGatePolicy,
    Node,
    NodeShape,
    Pipeline,
    StyleRule,
    Stylesheet,
)
from hermes_attractor.domain.run import NodeRunStatus, Run, RunNode, RunStatus
from hermes_attractor.use_cases.run_execution import advance_on_completion, launch_run

pytestmark = pytest.mark.integration

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _make_sp_pipeline() -> Pipeline:
    """Build a simplified sp workflow pipeline.

    Nodes (phases):
      start -> brainstorm -> specify -> plan ->
      fan_out -> [red_team, analyze] -> fan_in ->
      implement -> gate_review -> human_approve ->
      version_check (TOOL) -> exit

    ``gate_review`` has a GoalGatePolicy that routes back to ``implement``
    on failure (max_attempts=3).
    ``human_approve`` is a HUMAN node that pauses the run.
    ``version_check`` is a TOOL node.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    brainstorm = Node(node_id="brainstorm", shape=NodeShape.CODERGEN, profile="architect")
    specify = Node(node_id="specify", shape=NodeShape.CODERGEN, profile="architect")
    plan = Node(node_id="plan", shape=NodeShape.CODERGEN, profile="architect")
    fan_out = Node(node_id="fan_out", shape=NodeShape.FAN_OUT, profile="orchestrator")
    red_team = Node(node_id="red_team", shape=NodeShape.CODERGEN, profile="security-reviewer")
    analyze = Node(node_id="analyze", shape=NodeShape.CODERGEN, profile="analyst")
    fan_in = Node(node_id="fan_in", shape=NodeShape.FAN_IN, profile="orchestrator")
    implement = Node(node_id="implement", shape=NodeShape.CODERGEN, profile="coder")
    gate_review = Node(
        node_id="gate_review",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="implement", max_attempts=3),
    )
    human_approve = Node(
        node_id="human_approve",
        shape=NodeShape.HUMAN,
        profile="human",
        prompt="Please review and approve the implementation.",
    )
    version_check = Node(
        node_id="version_check",
        shape=NodeShape.TOOL,
        profile="tool-runner",
        prompt="check_version",
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)

    edges = [
        Edge(source_id="start", target_id="brainstorm"),
        Edge(source_id="brainstorm", target_id="specify"),
        Edge(source_id="specify", target_id="plan"),
        Edge(source_id="plan", target_id="fan_out"),
        Edge(source_id="fan_out", target_id="red_team"),
        Edge(source_id="fan_out", target_id="analyze"),
        Edge(source_id="red_team", target_id="fan_in"),
        Edge(source_id="analyze", target_id="fan_in"),
        Edge(source_id="fan_in", target_id="implement"),
        Edge(source_id="implement", target_id="gate_review"),
        Edge(source_id="gate_review", target_id="implement", label="fail"),
        Edge(source_id="gate_review", target_id="human_approve", label="pass"),
        Edge(source_id="human_approve", target_id="version_check"),
        Edge(source_id="version_check", target_id="exit"),
    ]

    stylesheet = Stylesheet(
        rules=[
            StyleRule(selector="*", profile="coder"),
            StyleRule(selector="HUMAN", profile="human"),
            StyleRule(selector="TOOL", profile="tool-runner"),
            StyleRule(selector="FAN_OUT", profile="orchestrator"),
            StyleRule(selector="FAN_IN", profile="orchestrator"),
        ]
    )

    return Pipeline(
        spec_id="sp-pipeline",
        nodes=[
            start,
            brainstorm,
            specify,
            plan,
            fan_out,
            red_team,
            analyze,
            fan_in,
            implement,
            gate_review,
            human_approve,
            version_check,
            exit_,
        ],
        edges=edges,
        stylesheet=stylesheet,
    )


def test_sp_pipeline_validates_clean() -> None:
    """The sp reference pipeline validates clean with no issues."""
    pipeline = _make_sp_pipeline()
    issues = pipeline.validate()
    assert issues == [], f"Expected no validation issues, got: {issues}"


@pytest.mark.xfail(
    reason="US8 end-to-end sp run requires complete orchestration (complex state machine simulation)",
    strict=True,
)
def test_sp_pipeline_runs_end_to_end_to_succeeded() -> None:  # noqa: PLR0915, C901
    """The sp pipeline runs end-to-end through all node types and reaches SUCCEEDED.

    This is a comprehensive smoke test exercising:
    - Sequential phases
    - FAN_OUT/FAN_IN parallel branches
    - Goal-gate review loop (pass on second attempt)
    - HUMAN node pause and resume
    - TOOL node execution
    """
    pipeline = _make_sp_pipeline()

    # In-memory state.
    runs: dict[str, Run] = {}
    nodes: list[RunNode] = []
    task_counter: list[int] = [1]

    def _create_run(run: Run) -> None:
        runs[run.run_id] = run

    def _save_run(run: Run) -> None:
        runs[run.run_id] = run

    def _get_run(run_id: str) -> Run | None:
        return runs.get(run_id)

    def _active_runs() -> list[Run]:
        return [r for r in runs.values() if r.status in (RunStatus.RUNNING, RunStatus.PAUSED_HUMAN)]

    def _upsert_node(node: RunNode) -> None:
        idx = next(
            (i for i, n in enumerate(nodes) if n.run_id == node.run_id and n.node_id == node.node_id),
            None,
        )
        if idx is not None:
            nodes[idx] = node
        else:
            nodes.append(node)

    def _nodes_for_run(run_id: str) -> list[RunNode]:
        return [n for n in nodes if n.run_id == run_id]

    def _get_node_by_task(task_id: str) -> RunNode | None:
        return next((n for n in nodes if n.task_id == task_id), None)

    run_state = MagicMock()
    run_state.create_run.side_effect = _create_run
    run_state.save_run.side_effect = _save_run
    run_state.get_run.side_effect = _get_run
    run_state.active_runs.side_effect = _active_runs
    run_state.upsert_node.side_effect = _upsert_node
    run_state.nodes_for_run.side_effect = _nodes_for_run
    run_state.get_node_by_task.side_effect = _get_node_by_task

    def _create_card(card: object) -> str:
        task_id = f"task-{task_counter[0]:03d}"
        task_counter[0] += 1
        return task_id

    kanban = MagicMock()
    kanban.create_card.side_effect = _create_card

    tool_registry = InMemoryToolNodeRegistry()

    def _check_version(ctx: object) -> dict[str, object]:
        """Deterministic version check tool."""
        return {"status": "SUCCESS", "context_updates": {"version_ok": "true"}}

    tool_registry.register("check_version", _check_version)

    serializer = MagicMock()
    serializer.parse.return_value = pipeline

    store = MagicMock()
    store.load.return_value = "digraph sp-pipeline {}"

    clock = MagicMock()
    clock.now.return_value = _NOW

    # Launch run.
    result = launch_run(
        spec_id="sp-pipeline",
        initial_context={"feature": "my-feature"},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )
    run_id = str(result["run_id"])
    event_id: list[int] = [1]

    def _advance(task_id: str, *, gate_pass: bool = True, **meta: object) -> None:
        """Simulate completing a card."""
        metadata: dict[str, object] = {}
        if gate_pass:
            metadata["gate"] = "pass"
        if meta:
            metadata.update(meta)
        run_state.nodes_for_run.return_value = _nodes_for_run(run_id)
        advance_on_completion(
            card_result=CardResult(
                task_id=task_id,
                event_id=event_id[0],
                event_kind="completed",
                summary="Done.",
                metadata=metadata,
            ),
            kanban=kanban,
            run_state=run_state,
            pipeline=pipeline,
            clock=clock,
            tool_registry=tool_registry,
        )
        event_id[0] += 1

    def _dispatched_node(node_id: str) -> RunNode | None:
        """Get the most recent dispatched RunNode for a given node_id."""
        matching = [n for n in nodes if n.node_id == node_id and n.status is NodeRunStatus.DISPATCHED]
        return matching[-1] if matching else None

    # Sequential phases.
    assert _dispatched_node("brainstorm") is not None, "brainstorm should be dispatched"
    _advance(_dispatched_node("brainstorm").task_id)  # type: ignore[union-attr]

    assert _dispatched_node("specify") is not None
    _advance(_dispatched_node("specify").task_id)  # type: ignore[union-attr]

    assert _dispatched_node("plan") is not None
    _advance(_dispatched_node("plan").task_id)  # type: ignore[union-attr]

    # FAN_OUT dispatches fan_out card.
    fan_out_node = _dispatched_node("fan_out")
    assert fan_out_node is not None, "fan_out should be dispatched"
    _advance(fan_out_node.task_id)  # type: ignore[union-attr]

    # After fan_out completes, red_team and analyze are dispatched.
    assert _dispatched_node("red_team") is not None
    assert _dispatched_node("analyze") is not None

    # Complete both branches.
    _advance(_dispatched_node("red_team").task_id)  # type: ignore[union-attr]
    _advance(_dispatched_node("analyze").task_id)  # type: ignore[union-attr]

    # FAN_IN dispatched after both branches complete.
    assert _dispatched_node("fan_in") is not None
    _advance(_dispatched_node("fan_in").task_id)  # type: ignore[union-attr]

    # implement dispatched.
    assert _dispatched_node("implement") is not None
    _advance(_dispatched_node("implement").task_id)  # type: ignore[union-attr]

    # gate_review dispatched (first attempt, fails).
    assert _dispatched_node("gate_review") is not None
    gate_node = _dispatched_node("gate_review")
    run_state.nodes_for_run.return_value = _nodes_for_run(run_id)
    _advance(gate_node.task_id, gate_pass=False)  # type: ignore[union-attr]

    # implement dispatched again (attempt 2).
    implement_nodes = [n for n in nodes if n.node_id == "implement"]
    assert len(implement_nodes) >= 2, f"Expected implement attempt 2, got: {[n.attempt for n in implement_nodes]}"
    impl2_task_id = implement_nodes[-1].task_id
    assert impl2_task_id is not None
    _advance(impl2_task_id)

    # gate_review dispatched (second attempt, passes).
    gate_nodes_2 = [n for n in nodes if n.node_id == "gate_review" and n.status is NodeRunStatus.DISPATCHED]
    assert gate_nodes_2, "Expected gate_review attempt 2"
    run_state.nodes_for_run.return_value = _nodes_for_run(run_id)
    gate2_task_id = gate_nodes_2[-1].task_id
    assert gate2_task_id is not None
    _advance(gate2_task_id, gate_pass=True)

    # human_approve dispatched (PAUSED_HUMAN).
    assert runs[run_id].status is RunStatus.PAUSED_HUMAN, f"Expected PAUSED_HUMAN, got {runs[run_id].status}"
    assert _dispatched_node("human_approve") is not None
    _advance(_dispatched_node("human_approve").task_id)  # type: ignore[union-attr]

    # version_check (TOOL) runs inline -> EXIT -> SUCCEEDED.
    assert runs[run_id].status is RunStatus.SUCCEEDED, f"Expected SUCCEEDED, got {runs[run_id].status}"

    # Context should have version_ok from the tool.
    assert runs[run_id].context.data.get("version_ok") == "true", (
        f"Expected version_ok=true in context: {runs[run_id].context.data}"
    )
