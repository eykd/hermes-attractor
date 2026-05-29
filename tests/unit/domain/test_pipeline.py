"""Unit tests for the Pipeline domain model (NodeShape, Node, GoalGatePolicy, Edge, Stylesheet, Pipeline).

These tests constitute the RED phase for M1 (authoring core). They fail until
src/hermes_attractor/domain/pipeline.py is implemented.
"""

from __future__ import annotations

import pytest

from hermes_attractor.domain.pipeline import (
    Edge,
    GoalGatePolicy,
    Node,
    NodeShape,
    Pipeline,
    StyleRule,
    Stylesheet,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# NodeShape
# ---------------------------------------------------------------------------


def test_node_shape_has_all_required_members() -> None:
    """NodeShape enum must declare START, EXIT, CODERGEN, CONDITIONAL, TOOL, FAN_OUT, FAN_IN, HUMAN."""
    required = {"START", "EXIT", "CODERGEN", "CONDITIONAL", "TOOL", "FAN_OUT", "FAN_IN", "HUMAN"}
    actual = {member.name for member in NodeShape}
    assert required.issubset(actual), f"Missing NodeShape members: {required - actual}"


def test_node_shape_dot_attribute() -> None:
    """Each NodeShape must expose a dot_shape string attribute."""
    assert hasattr(NodeShape.START, "dot_shape"), "NodeShape.START missing dot_shape"
    assert NodeShape.START.dot_shape == "Mdiamond"
    assert NodeShape.EXIT.dot_shape == "Msquare"
    assert NodeShape.CODERGEN.dot_shape == "box"
    assert NodeShape.CONDITIONAL.dot_shape == "diamond"


# ---------------------------------------------------------------------------
# GoalGatePolicy
# ---------------------------------------------------------------------------


def test_goal_gate_policy_has_retry_target_and_max_attempts() -> None:
    """GoalGatePolicy must have retry_target and max_attempts."""
    policy = GoalGatePolicy(retry_target="plan", max_attempts=3)
    assert policy.retry_target == "plan"
    assert policy.max_attempts == 3


def test_goal_gate_policy_rejects_zero_max_attempts() -> None:
    """GoalGatePolicy must reject max_attempts < 1."""
    with pytest.raises((ValueError, Exception)):
        _ = GoalGatePolicy(retry_target="plan", max_attempts=0)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


def test_node_has_required_fields() -> None:
    """Node must have node_id, shape, prompt, profile, retry_limit, goal_gate, node_class."""
    node = Node(node_id="start", shape=NodeShape.START)
    assert node.node_id == "start"
    assert node.shape is NodeShape.START
    assert node.prompt is None
    assert node.profile is None
    assert node.retry_limit >= 0
    assert node.goal_gate is None
    assert node.node_class is None


def test_node_with_all_optional_fields() -> None:
    """Node accepts prompt, profile, retry_limit, goal_gate, and node_class."""
    policy = GoalGatePolicy(retry_target="plan", max_attempts=2)
    node = Node(
        node_id="impl",
        shape=NodeShape.CODERGEN,
        prompt="Do the work.",
        profile="coder",
        retry_limit=3,
        goal_gate=policy,
        node_class="worker",
    )
    assert node.prompt == "Do the work."
    assert node.profile == "coder"
    assert node.retry_limit == 3
    assert node.goal_gate is policy
    assert node.node_class == "worker"


def test_node_rejects_empty_node_id() -> None:
    """Node must reject an empty node_id."""
    with pytest.raises((ValueError, Exception)):
        _ = Node(node_id="", shape=NodeShape.CODERGEN)


def test_node_rejects_negative_retry_limit() -> None:
    """Node must reject retry_limit < 0."""
    with pytest.raises((ValueError, Exception)):
        _ = Node(node_id="n", shape=NodeShape.CODERGEN, retry_limit=-1)


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------


def test_edge_has_required_fields() -> None:
    """Edge must have source_id, target_id and optional condition/label/weight."""
    edge = Edge(source_id="a", target_id="b")
    assert edge.source_id == "a"
    assert edge.target_id == "b"
    assert edge.condition is None
    assert edge.label is None
    assert edge.weight == 0


def test_edge_with_optional_fields() -> None:
    """Edge accepts condition, label, and weight."""
    edge = Edge(source_id="a", target_id="b", condition="x == 1", label="yes", weight=5)
    assert edge.condition == "x == 1"
    assert edge.label == "yes"
    assert edge.weight == 5


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------


def test_stylesheet_resolve_returns_none_for_empty_rules() -> None:
    """Stylesheet with no rules returns None for any node."""
    ss = Stylesheet(rules=[])
    node = Node(node_id="n", shape=NodeShape.CODERGEN)
    assert ss.resolve(node) is None


def test_stylesheet_resolve_universal_selector() -> None:
    """Universal selector (*) matches any node."""
    ss = Stylesheet(rules=[StyleRule(selector="*", profile="default")])
    node = Node(node_id="n", shape=NodeShape.CODERGEN)
    assert ss.resolve(node) == "default"


def test_stylesheet_resolve_shape_selector() -> None:
    """Shape selector matches nodes of that shape."""
    ss = Stylesheet(
        rules=[
            StyleRule(selector="*", profile="default"),
            StyleRule(selector="CODERGEN", profile="coder"),
        ]
    )
    codergen = Node(node_id="n", shape=NodeShape.CODERGEN)
    conditional = Node(node_id="c", shape=NodeShape.CONDITIONAL)
    assert ss.resolve(codergen) == "coder"
    assert ss.resolve(conditional) == "default"


def test_stylesheet_resolve_class_beats_shape() -> None:
    """Class selector (.classname) takes precedence over shape selector."""
    ss = Stylesheet(
        rules=[
            StyleRule(selector="CODERGEN", profile="generic-coder"),
            StyleRule(selector=".fast", profile="fast-coder"),
        ]
    )
    node_with_class = Node(node_id="n", shape=NodeShape.CODERGEN, node_class="fast")
    assert ss.resolve(node_with_class) == "fast-coder"


def test_stylesheet_resolve_id_beats_class() -> None:
    """ID selector (#node_id) takes precedence over class selector."""
    ss = Stylesheet(
        rules=[
            StyleRule(selector=".fast", profile="fast-coder"),
            StyleRule(selector="#special", profile="special-coder"),
        ]
    )
    node = Node(node_id="special", shape=NodeShape.CODERGEN, node_class="fast")
    assert ss.resolve(node) == "special-coder"


def test_stylesheet_resolve_last_rule_wins_tiebreak() -> None:
    """When two rules have equal specificity, the last one wins."""
    ss = Stylesheet(
        rules=[
            StyleRule(selector="*", profile="first"),
            StyleRule(selector="*", profile="second"),
        ]
    )
    node = Node(node_id="n", shape=NodeShape.CODERGEN)
    assert ss.resolve(node) == "second"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _make_simple_pipeline() -> Pipeline:
    """Build a minimal valid pipeline (start -> work -> exit)."""
    nodes = [
        Node(node_id="start", shape=NodeShape.START),
        Node(node_id="work", shape=NodeShape.CODERGEN, profile="worker"),
        Node(node_id="exit", shape=NodeShape.EXIT),
    ]
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="exit"),
    ]
    return Pipeline(spec_id="test", nodes=nodes, edges=edges, stylesheet=Stylesheet(rules=[]))


def test_pipeline_validate_returns_empty_for_valid_graph() -> None:
    """Pipeline.validate() returns [] for a valid graph."""
    pipeline = _make_simple_pipeline()
    issues = pipeline.validate()
    assert issues == [], f"Expected no issues for valid pipeline, got: {issues}"


def test_pipeline_validate_reports_missing_start_node() -> None:
    """Pipeline.validate() reports an issue when there is no START node."""
    nodes = [
        Node(node_id="work", shape=NodeShape.CODERGEN, profile="worker"),
        Node(node_id="exit", shape=NodeShape.EXIT),
    ]
    edges = [Edge(source_id="work", target_id="exit")]
    pipeline = Pipeline(spec_id="test", nodes=nodes, edges=edges, stylesheet=Stylesheet(rules=[]))
    issues = pipeline.validate()
    assert issues, "Expected at least one issue for missing START node"
    assert any("start" in str(issue).lower() or "START" in str(issue) for issue in issues), (
        f"Expected an issue mentioning START node: {issues}"
    )


def test_pipeline_validate_reports_dangling_edge() -> None:
    """Pipeline.validate() reports an issue for an edge to a nonexistent node."""
    nodes = [
        Node(node_id="start", shape=NodeShape.START),
        Node(node_id="exit", shape=NodeShape.EXIT),
    ]
    edges = [
        Edge(source_id="start", target_id="ghost"),
        Edge(source_id="start", target_id="exit"),
    ]
    pipeline = Pipeline(spec_id="test", nodes=nodes, edges=edges, stylesheet=Stylesheet(rules=[]))
    issues = pipeline.validate()
    assert issues, "Expected at least one issue for dangling edge to 'ghost'"
    assert any("ghost" in str(issue) for issue in issues), f"Expected issue referencing 'ghost': {issues}"


def test_pipeline_resolve_profile_uses_node_override() -> None:
    """Pipeline.resolve_profile returns node.profile when set (FR-019)."""
    ss = Stylesheet(rules=[StyleRule(selector="*", profile="default")])
    node = Node(node_id="n", shape=NodeShape.CODERGEN, profile="override")
    pipeline = Pipeline(
        spec_id="test",
        nodes=[
            Node(node_id="start", shape=NodeShape.START),
            node,
            Node(node_id="exit", shape=NodeShape.EXIT),
        ],
        edges=[
            Edge(source_id="start", target_id="n"),
            Edge(source_id="n", target_id="exit"),
        ],
        stylesheet=ss,
    )
    assert pipeline.resolve_profile(node) == "override"


def test_pipeline_resolve_profile_falls_back_to_stylesheet() -> None:
    """Pipeline.resolve_profile falls back to stylesheet when node has no profile."""
    ss = Stylesheet(rules=[StyleRule(selector="*", profile="default")])
    node = Node(node_id="n", shape=NodeShape.CODERGEN)
    pipeline = Pipeline(
        spec_id="test",
        nodes=[
            Node(node_id="start", shape=NodeShape.START),
            node,
            Node(node_id="exit", shape=NodeShape.EXIT),
        ],
        edges=[
            Edge(source_id="start", target_id="n"),
            Edge(source_id="n", target_id="exit"),
        ],
        stylesheet=ss,
    )
    assert pipeline.resolve_profile(node) == "default"


def test_stylesheet_resolve_unknown_selector_returns_none() -> None:
    """An unknown selector that is not a valid NodeShape name returns None."""
    ss = Stylesheet(rules=[StyleRule(selector="UNKNOWNSHAPE", profile="x")])
    node = Node(node_id="n", shape=NodeShape.CODERGEN)
    assert ss.resolve(node) is None


def test_stylesheet_resolve_shape_no_match_returns_none() -> None:
    """A shape selector that doesn't match the node's shape returns None (no other rules)."""
    ss = Stylesheet(rules=[StyleRule(selector="CONDITIONAL", profile="router")])
    node = Node(node_id="n", shape=NodeShape.CODERGEN)
    assert ss.resolve(node) is None


def test_pipeline_validate_reports_missing_exit_node() -> None:
    """Pipeline.validate() reports an issue when there is no EXIT node."""
    nodes = [
        Node(node_id="start", shape=NodeShape.START),
        Node(node_id="work", shape=NodeShape.CODERGEN, profile="worker"),
    ]
    edges = [Edge(source_id="start", target_id="work")]
    pipeline = Pipeline(spec_id="test", nodes=nodes, edges=edges, stylesheet=Stylesheet(rules=[]))
    issues = pipeline.validate()
    assert issues, "Expected at least one issue for missing EXIT node"
    assert any("EXIT" in str(issue) for issue in issues), f"Expected an issue mentioning EXIT node: {issues}"


def test_pipeline_validate_reports_dangling_source_edge() -> None:
    """Pipeline.validate() reports an issue for an edge from a nonexistent source node."""
    nodes = [
        Node(node_id="start", shape=NodeShape.START),
        Node(node_id="exit", shape=NodeShape.EXIT),
    ]
    edges = [
        Edge(source_id="ghost_source", target_id="exit"),
        Edge(source_id="start", target_id="exit"),
    ]
    pipeline = Pipeline(spec_id="test", nodes=nodes, edges=edges, stylesheet=Stylesheet(rules=[]))
    issues = pipeline.validate()
    assert issues, "Expected at least one issue for dangling source edge"
    assert any("ghost_source" in str(issue) for issue in issues), f"Expected issue referencing 'ghost_source': {issues}"


def test_pipeline_validate_reports_unreachable_node() -> None:
    """Pipeline.validate() reports an issue for a node not reachable from START."""
    nodes = [
        Node(node_id="start", shape=NodeShape.START),
        Node(node_id="work", shape=NodeShape.CODERGEN, profile="worker"),
        Node(node_id="orphan", shape=NodeShape.CODERGEN, profile="worker"),
        Node(node_id="exit", shape=NodeShape.EXIT),
    ]
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="exit"),
    ]
    pipeline = Pipeline(spec_id="test", nodes=nodes, edges=edges, stylesheet=Stylesheet(rules=[]))
    issues = pipeline.validate()
    assert issues, "Expected at least one issue for unreachable node 'orphan'"
    assert any("orphan" in str(issue) for issue in issues), f"Expected issue referencing 'orphan': {issues}"


def test_pipeline_validate_reports_goal_gate_retry_target_unreachable() -> None:
    """Pipeline.validate() reports an issue when a goal gate retry_target is unreachable."""
    nodes = [
        Node(node_id="start", shape=NodeShape.START),
        Node(
            node_id="work",
            shape=NodeShape.CODERGEN,
            profile="worker",
            goal_gate=GoalGatePolicy(retry_target="orphan", max_attempts=2),
        ),
        Node(node_id="orphan", shape=NodeShape.CODERGEN, profile="worker"),
        Node(node_id="exit", shape=NodeShape.EXIT),
    ]
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="exit"),
    ]
    pipeline = Pipeline(spec_id="test", nodes=nodes, edges=edges, stylesheet=Stylesheet(rules=[]))
    issues = pipeline.validate()
    assert any("orphan" in str(issue) for issue in issues), (
        f"Expected issue mentioning unreachable retry_target 'orphan': {issues}"
    )


def test_bfs_handles_revisited_nodes() -> None:
    """BFS reachability correctly handles graphs where multiple paths lead to the same node."""
    nodes = [
        Node(node_id="start", shape=NodeShape.START),
        Node(node_id="a", shape=NodeShape.CODERGEN, profile="worker"),
        Node(node_id="b", shape=NodeShape.CODERGEN, profile="worker"),
        Node(node_id="merge", shape=NodeShape.CODERGEN, profile="worker"),
        Node(node_id="exit", shape=NodeShape.EXIT),
    ]
    edges = [
        Edge(source_id="start", target_id="a"),
        Edge(source_id="start", target_id="b"),
        Edge(source_id="a", target_id="merge"),
        Edge(source_id="b", target_id="merge"),
        Edge(source_id="merge", target_id="exit"),
    ]
    pipeline = Pipeline(spec_id="test", nodes=nodes, edges=edges, stylesheet=Stylesheet(rules=[]))
    issues = pipeline.validate()
    assert issues == [], f"Expected no issues for a valid diamond-shaped pipeline, got: {issues}"


def test_pipeline_validate_goal_gate_retry_target_nonexistent() -> None:
    """Pipeline.validate() reports an issue when goal gate retry_target does not exist."""
    nodes = [
        Node(node_id="start", shape=NodeShape.START),
        Node(
            node_id="work",
            shape=NodeShape.CODERGEN,
            profile="worker",
            goal_gate=GoalGatePolicy(retry_target="nonexistent_node", max_attempts=2),
        ),
        Node(node_id="exit", shape=NodeShape.EXIT),
    ]
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="exit"),
    ]
    pipeline = Pipeline(spec_id="test", nodes=nodes, edges=edges, stylesheet=Stylesheet(rules=[]))
    issues = pipeline.validate()
    assert issues, "Expected at least one issue for nonexistent goal gate retry_target"
    assert any("nonexistent_node" in str(issue) for issue in issues), (
        f"Expected issue referencing 'nonexistent_node': {issues}"
    )


def test_pipeline_validate_valid_goal_gate_passes() -> None:
    """Pipeline.validate() has no issue when a goal gate retry_target is a reachable node."""
    nodes = [
        Node(node_id="start", shape=NodeShape.START),
        Node(
            node_id="work",
            shape=NodeShape.CODERGEN,
            profile="worker",
            goal_gate=GoalGatePolicy(retry_target="start", max_attempts=3),
        ),
        Node(node_id="exit", shape=NodeShape.EXIT),
    ]
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="exit"),
    ]
    pipeline = Pipeline(spec_id="test", nodes=nodes, edges=edges, stylesheet=Stylesheet(rules=[]))
    issues = pipeline.validate()
    assert issues == [], f"Expected no issues for valid goal gate, got: {issues}"
