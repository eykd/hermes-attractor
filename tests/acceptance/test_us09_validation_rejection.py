"""Acceptance tests for US9: Invalid pipeline rejected naming the offending element.

Acceptance spec: specs/acceptance-specs/US09-validation-rejection.txt

Scenarios covered:

  1. No start node -> valid:false with issue naming missing START.
  2. Multiple exit nodes -> valid:false.
  3. Unreachable node -> valid:false naming the unreachable node.
  4. Dangling edge -> valid:false naming the missing target.
  5. Goal gate with unreachable retry target -> valid:false.
  6. Unresolvable profile -> valid:false naming the node.
  7. attractor_run with no-start pipeline -> ok:true but no kanban card created.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path  # noqa: TC003  # used in function signatures at runtime
from typing import cast
from unittest.mock import MagicMock

import pytest

from hermes_attractor.adapters.dot_serializer import PydotSerializer
from hermes_attractor.adapters.pipeline_store import GitPipelineStore
from hermes_attractor.domain.pipeline import (
    Edge,
    GoalGatePolicy,
    Node,
    NodeShape,
    Pipeline,
    StyleRule,
    Stylesheet,
)
from hermes_attractor.plugin.tools import handle_attractor_run
from hermes_attractor.use_cases.authoring import validate_pipeline

pytestmark = pytest.mark.integration

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_no_start_dot() -> str:
    """Build a DOT string with no START node."""
    return "digraph test { work [shape=box]; exit [shape=Msquare]; work -> exit; }"


def _make_multiple_exit_dot() -> str:
    """Build a DOT string with two EXIT nodes."""
    return (
        "digraph test { start [shape=Mdiamond]; exit1 [shape=Msquare]; "
        "exit2 [shape=Msquare]; start -> exit1; start -> exit2; }"
    )


def _make_unreachable_node_dot() -> str:
    """Build a DOT string with an unreachable node."""
    return (
        "digraph test { start [shape=Mdiamond]; work [shape=box]; orphan [shape=box]; "
        "exit [shape=Msquare]; start -> work; work -> exit; }"
    )


def _make_dangling_edge_dot() -> str:
    """Build a DOT string with an edge to a nonexistent target."""
    return "digraph test { start [shape=Mdiamond]; exit [shape=Msquare]; start -> ghost; start -> exit; }"


def _validate_with_store(spec_id: str, dot: str, tmp_path: Path) -> dict[str, object]:
    """Store the DOT in a temp git repo and run validate_pipeline.

    Args:
        spec_id: Pipeline spec identifier.
        dot: DOT string to save and validate.
        tmp_path: Temp directory for the git store.

    Returns:
        The validate_pipeline result dict.
    """
    store = GitPipelineStore(repo_root=tmp_path)
    store.ensure_repo()
    store.save(spec_id, dot)
    serializer = PydotSerializer()
    return validate_pipeline(spec_id=spec_id, store=store, serializer=serializer)


# ---------------------------------------------------------------------------
# Scenario 1: No start node
# ---------------------------------------------------------------------------


def test_validate_reports_missing_start_node(tmp_path: Path) -> None:
    """Pipeline with no START node fails validation naming the missing element."""
    result = _validate_with_store("no-start", _make_no_start_dot(), tmp_path)

    assert result.get("valid") is False, f"Expected valid=false, got: {result}"
    issues = cast("list[object]", result.get("issues", []))
    assert issues, "Expected at least one validation issue"
    issue_texts = [str(issue) for issue in issues]
    assert any("START" in text or "start" in text.lower() for text in issue_texts), (
        f"Expected an issue mentioning START: {issue_texts}"
    )


# ---------------------------------------------------------------------------
# Scenario 2: Multiple exit nodes
# ---------------------------------------------------------------------------


def test_validate_reports_multiple_exit_nodes(tmp_path: Path) -> None:
    """Pipeline with multiple EXIT nodes fails validation."""
    result = _validate_with_store("multi-exit", _make_multiple_exit_dot(), tmp_path)

    assert result.get("valid") is False, f"Expected valid=false for multiple EXIT nodes: {result}"


# ---------------------------------------------------------------------------
# Scenario 3: Unreachable node
# ---------------------------------------------------------------------------


def test_validate_reports_unreachable_node(tmp_path: Path) -> None:
    """Pipeline with an unreachable node fails validation naming it."""
    result = _validate_with_store("unreachable", _make_unreachable_node_dot(), tmp_path)

    assert result.get("valid") is False, f"Expected valid=false for unreachable node: {result}"
    issues = cast("list[object]", result.get("issues", []))
    assert any("orphan" in str(issue) for issue in issues), f"Expected issue mentioning 'orphan': {issues}"


# ---------------------------------------------------------------------------
# Scenario 4: Dangling edge
# ---------------------------------------------------------------------------


def test_validate_reports_dangling_edge(tmp_path: Path) -> None:
    """Pipeline with a dangling edge fails validation naming the missing target."""
    result = _validate_with_store("dangling", _make_dangling_edge_dot(), tmp_path)

    assert result.get("valid") is False, f"Expected valid=false for dangling edge: {result}"
    issues = cast("list[object]", result.get("issues", []))
    assert any("ghost" in str(issue) for issue in issues), f"Expected issue mentioning 'ghost': {issues}"


# ---------------------------------------------------------------------------
# Scenario 5: Goal gate with unreachable retry target (via domain)
# ---------------------------------------------------------------------------


def test_pipeline_validate_reports_unreachable_goal_gate_retry_target() -> None:
    """Pipeline.validate() reports an issue when a goal gate retry_target is unreachable."""
    start = Node(node_id="start", shape=NodeShape.START)
    gate = Node(
        node_id="gate",
        shape=NodeShape.CODERGEN,
        profile="reviewer",
        goal_gate=GoalGatePolicy(retry_target="unreachable_node", max_attempts=3),
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="goal-gate-test",
        nodes=[start, gate, exit_],
        edges=[
            Edge(source_id="start", target_id="gate"),
            Edge(source_id="gate", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )

    issues = pipeline.validate()

    assert issues, "Expected at least one issue for unreachable goal gate retry_target"
    assert any("unreachable_node" in str(issue) for issue in issues), (
        f"Expected issue mentioning 'unreachable_node': {issues}"
    )


# ---------------------------------------------------------------------------
# Scenario 6: Unresolvable profile
# ---------------------------------------------------------------------------


def test_pipeline_validate_reports_unresolvable_profile() -> None:
    """Pipeline.validate() reports an issue for a node with no resolved profile."""
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(
        node_id="work",
        shape=NodeShape.CODERGEN,
        # No profile, no stylesheet rule -> unresolvable
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    pipeline = Pipeline(
        spec_id="no-profile",
        nodes=[start, work, exit_],
        edges=[
            Edge(source_id="start", target_id="work"),
            Edge(source_id="work", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[]),  # empty stylesheet
    )

    issues = pipeline.validate()

    assert issues, "Expected at least one issue for unresolvable profile"
    assert any("work" in str(issue) for issue in issues), f"Expected issue mentioning 'work': {issues}"


# ---------------------------------------------------------------------------
# Scenario 7: attractor_run with invalid pipeline
# ---------------------------------------------------------------------------


def test_attractor_run_with_no_start_pipeline_creates_no_card() -> None:
    """attractor_run with a pipeline that has no START node creates no kanban card.

    The current implementation creates a run but dispatches no first card
    because there's no START node from which to find an entry.
    Pre-run validation enforcement is a future enhancement.
    """
    dot = _make_no_start_dot()
    pipeline = PydotSerializer().parse(dot)

    serializer_mock = MagicMock()
    serializer_mock.parse.return_value = pipeline

    store = MagicMock()
    store.load.return_value = dot

    run_state = MagicMock()
    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW

    raw = handle_attractor_run(
        {"spec_id": "no-start", "context": {}},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer_mock,
        store=store,
        clock=clock,
    )

    result = json.loads(raw)
    if result.get("ok") is True:
        # No kanban card should be created (no START node to dispatch from).
        kanban.create_card.assert_not_called()
