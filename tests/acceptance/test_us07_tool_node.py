"""Acceptance tests for US7: Tool node runs deterministic work into context.

Acceptance spec: specs/acceptance-specs/US07-tool-node.txt

Scenarios covered:

  1. GIVEN a pipeline with a TOOL node and a registered tool
     WHEN traversal reaches the TOOL node
     THEN the tool is invoked with context and its result updates context.

  2. GIVEN a pipeline with a TOOL node referencing an unknown tool
     WHEN attractor_validate is called
     THEN validation fails with a structured issue.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.card import CardResult
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

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xfail(
        reason="TOOL node dispatch in advance_on_completion not yet implemented (US7)",
        strict=True,
    ),
]

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
_LATER = datetime.datetime(2026, 1, 1, second=10, tzinfo=datetime.UTC)


def _make_tool_pipeline(tool_name: str = "my_tool") -> Pipeline:
    """Build: start -> work -> tool_stage -> exit.

    ``tool_stage`` is a TOOL node that should invoke ``tool_name``.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    tool_stage = Node(
        node_id="tool_stage",
        shape=NodeShape.TOOL,
        profile="tool-runner",
        prompt=tool_name,  # prompt holds the tool name for TOOL nodes
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="tool_stage"),
        Edge(source_id="tool_stage", target_id="exit"),
    ]
    return Pipeline(
        spec_id="tool-pipeline",
        nodes=[start, work, tool_stage, exit_],
        edges=edges,
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def _make_run(run_id: str = "run1") -> Run:
    """Build a minimal Run."""
    return Run(
        run_id=run_id,
        spec_id="tool-pipeline",
        status=RunStatus.RUNNING,
        context=Context(data={"input": "raw_data"}),
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_tool_node_invokes_registered_tool_and_updates_context() -> None:
    """TOOL node invokes the registered tool and applies its context updates.

    GIVEN a pipeline with a TOOL node
    WHEN traversal reaches the TOOL node (work completes)
    THEN the tool is invoked with the current context
    THEN the tool's context_updates are applied to the run context
    THEN traversal continues toward exit.
    """
    pipeline = _make_tool_pipeline(tool_name="my_tool")
    run = _make_run()
    work_record = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
    )

    # Tool registry: "my_tool" returns context_updates {"processed": "yes"}.
    def _my_tool(context: Context) -> object:
        """A simple deterministic test tool."""
        _ = context
        # Outcome not yet implemented — return a dict for now.
        return {"status": "SUCCESS", "context_updates": {"processed": "yes"}}

    tool_registry = MagicMock()
    tool_registry.run.return_value = _my_tool(run.context)

    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-work",
        event_id=1,
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
        tool_registry=tool_registry,  # type: ignore[call-arg]  # not yet in signature
    )

    # Tool should have been invoked.
    tool_registry.run.assert_called()
    call_args = tool_registry.run.call_args
    assert "my_tool" in str(call_args) or call_args[0][0] == "my_tool", (
        f"Expected tool 'my_tool' to be invoked, got: {call_args}"
    )

    # Context should have been updated.
    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.context.data.get("processed") == "yes", (
        f"Expected context to include 'processed=yes', got: {saved_run.context.data}"
    )


def test_tool_node_reaches_exit_after_tool_execution() -> None:
    """TOOL node execution proceeds directly to exit (no kanban card created).

    TOOL nodes are deterministic — they don't create kanban cards.
    After execution, traversal continues to the next node.
    """
    pipeline = _make_tool_pipeline(tool_name="fast_tool")
    run = _make_run()
    work_record = RunNode(
        run_id="run1",
        node_id="work",
        task_id="task-work",
        status=NodeRunStatus.RUNNING,
        attempt=1,
        parent_node_ids=["start"],
    )

    tool_registry = MagicMock()
    run_state = MagicMock()
    run_state.get_node_by_task.return_value = work_record
    run_state.get_run.return_value = run

    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _LATER

    card_result = CardResult(
        task_id="task-work",
        event_id=1,
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
        tool_registry=tool_registry,  # type: ignore[call-arg]
    )

    # TOOL node runs inline — no kanban card for the tool stage itself.
    # After tool, traversal reaches EXIT, so run should be SUCCEEDED.
    run_state.save_run.assert_called()
    saved_run: Run = run_state.save_run.call_args[0][0]
    assert saved_run.status is RunStatus.SUCCEEDED, f"Expected SUCCEEDED after TOOL->EXIT, got {saved_run.status}"
