"""Unit tests for the DotSerializer port and pydot adapter (RED phase for M1).

Tests fail until ports/dot.py and adapters/dot_serializer.py are implemented.
"""

from __future__ import annotations

import pytest

from hermes_attractor.adapters.dot_serializer import PydotSerializer
from hermes_attractor.domain.exceptions import PipelineValidationError
from hermes_attractor.domain.pipeline import Edge, Node, NodeShape, Pipeline, StyleRule, Stylesheet
from hermes_attractor.ports.dot import DotSerializer

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# A minimal DOT string for a valid 2-node pipeline.
# ---------------------------------------------------------------------------
_MINIMAL_DOT = """
digraph test_pipeline {
    start [shape=Mdiamond];
    exit [shape=Msquare];
    start -> exit;
}
""".strip()


# ---------------------------------------------------------------------------
# Port contract
# ---------------------------------------------------------------------------


def test_dot_serializer_protocol_has_parse_and_emit() -> None:
    """DotSerializer Protocol must declare parse and emit methods."""
    assert hasattr(DotSerializer, "parse"), "DotSerializer missing parse method"
    assert hasattr(DotSerializer, "emit"), "DotSerializer missing emit method"
    assert callable(DotSerializer.parse)
    assert callable(DotSerializer.emit)


def test_pydot_serializer_parse_returns_pipeline() -> None:
    """PydotSerializer.parse returns a Pipeline with the correct nodes."""
    serializer = PydotSerializer()
    pipeline = serializer.parse(_MINIMAL_DOT)
    node_ids = {n.node_id for n in pipeline.nodes}
    assert "start" in node_ids
    assert "exit" in node_ids


def test_pydot_serializer_parse_returns_pipeline_with_edges() -> None:
    """PydotSerializer.parse returns a Pipeline with the correct edges."""
    serializer = PydotSerializer()
    pipeline = serializer.parse(_MINIMAL_DOT)
    edge_pairs = {(e.source_id, e.target_id) for e in pipeline.edges}
    assert ("start", "exit") in edge_pairs


def test_pydot_serializer_parse_sets_node_shapes() -> None:
    """PydotSerializer.parse maps DOT shape attributes to NodeShape enum values."""
    serializer = PydotSerializer()
    pipeline = serializer.parse(_MINIMAL_DOT)
    node_map = {n.node_id: n for n in pipeline.nodes}
    assert node_map["start"].shape is NodeShape.START
    assert node_map["exit"].shape is NodeShape.EXIT


def test_pydot_serializer_emit_returns_dot_string() -> None:
    """PydotSerializer.emit returns a non-empty DOT string."""
    serializer = PydotSerializer()
    pipeline = Pipeline(
        spec_id="test",
        nodes=[
            Node(node_id="start", shape=NodeShape.START),
            Node(node_id="exit", shape=NodeShape.EXIT),
        ],
        edges=[Edge(source_id="start", target_id="exit")],
        stylesheet=Stylesheet(rules=[]),
    )
    dot = serializer.emit(pipeline)
    assert isinstance(dot, str)
    assert "start" in dot
    assert "exit" in dot


# ---------------------------------------------------------------------------
# Round-trip stability
# ---------------------------------------------------------------------------


def test_pydot_serializer_roundtrip_is_structurally_stable() -> None:
    """emit(parse(dot)) produces a structurally equivalent pipeline."""
    serializer = PydotSerializer()
    pipeline1 = serializer.parse(_MINIMAL_DOT)
    dot2 = serializer.emit(pipeline1)
    pipeline2 = serializer.parse(dot2)
    node_ids_1 = {n.node_id for n in pipeline1.nodes}
    node_ids_2 = {n.node_id for n in pipeline2.nodes}
    assert node_ids_1 == node_ids_2
    edges_1 = {(e.source_id, e.target_id) for e in pipeline1.edges}
    edges_2 = {(e.source_id, e.target_id) for e in pipeline2.edges}
    assert edges_1 == edges_2


# ---------------------------------------------------------------------------
# Resource limit enforcement
# ---------------------------------------------------------------------------


def test_pydot_serializer_parse_rejects_input_over_1mib() -> None:
    """PydotSerializer.parse raises PipelineValidationError for input > 1 MiB."""
    serializer = PydotSerializer()
    large_dot = "a" * (1024 * 1024 + 1)
    with pytest.raises(PipelineValidationError):
        _ = serializer.parse(large_dot)


def test_pydot_serializer_parse_rejects_graph_with_over_256_nodes() -> None:
    """PydotSerializer.parse raises PipelineValidationError for graphs with >256 nodes."""
    serializer = PydotSerializer()
    node_lines = "\n".join(f"    n{i} [shape=box];" for i in range(257))
    large_graph_dot = f"digraph huge {{\n{node_lines}\n}}"
    with pytest.raises(PipelineValidationError):
        _ = serializer.parse(large_graph_dot)


def test_pydot_serializer_parse_rejects_graph_with_over_1024_edges() -> None:
    """PydotSerializer.parse raises PipelineValidationError for graphs with >1024 edges."""
    serializer = PydotSerializer()
    node_lines = "\n".join(f"    n{i} [shape=box];" for i in range(50))
    edge_lines = "\n".join(f"    n{i % 50} -> n{(i + 1) % 50};" for i in range(1025))
    large_graph_dot = f"digraph huge {{\n{node_lines}\n{edge_lines}\n}}"
    with pytest.raises(PipelineValidationError):
        _ = serializer.parse(large_graph_dot)


def test_pydot_serializer_parse_rejects_empty_input() -> None:
    """PydotSerializer.parse raises PipelineValidationError for empty/invalid DOT input."""
    serializer = PydotSerializer()
    with pytest.raises(PipelineValidationError):
        _ = serializer.parse("")


def test_pydot_serializer_parse_and_emit_with_all_optional_node_attrs() -> None:
    """PydotSerializer roundtrip preserves profile, prompt, node_class, and retry_limit."""
    full_dot = """
digraph test {
    start [shape=Mdiamond];
    work [shape=box, profile="coder", prompt="Do it.", class="worker", retry_limit=3];
    exit [shape=Msquare];
    start -> work;
    work -> exit;
}
""".strip()
    serializer = PydotSerializer()
    pipeline = serializer.parse(full_dot)
    work_node = next(n for n in pipeline.nodes if n.node_id == "work")
    assert work_node.profile == "coder"
    assert work_node.prompt == "Do it."
    assert work_node.node_class == "worker"
    assert work_node.retry_limit == 3

    dot_out = serializer.emit(pipeline)
    pipeline2 = serializer.parse(dot_out)
    work2 = next(n for n in pipeline2.nodes if n.node_id == "work")
    assert work2.profile == "coder"
    assert work2.retry_limit == 3


def test_pydot_serializer_parse_and_emit_with_edge_attrs() -> None:
    """PydotSerializer roundtrip preserves edge condition, label, and weight."""
    edge_dot = """
digraph test {
    start [shape=Mdiamond];
    exit [shape=Msquare];
    start -> exit [condition="done == true", label="yes", weight=5];
}
""".strip()
    serializer = PydotSerializer()
    pipeline = serializer.parse(edge_dot)
    edge = next(iter(pipeline.edges))
    assert edge.condition == "done == true"
    assert edge.label == "yes"
    assert edge.weight == 5

    dot_out = serializer.emit(pipeline)
    pipeline2 = serializer.parse(dot_out)
    edge2 = next(iter(pipeline2.edges))
    assert edge2.condition == "done == true"
    assert edge2.weight == 5


def test_pydot_serializer_roundtrip_with_embedded_double_quote_in_prompt() -> None:
    """emit() -> parse() preserves prompt values containing embedded double-quotes."""
    serializer = PydotSerializer()
    pipeline = Pipeline(
        spec_id="quote_test",
        nodes=[
            Node(node_id="start", shape=NodeShape.START),
            Node(node_id="work", shape=NodeShape.CODERGEN, prompt='Say "hello"'),
            Node(node_id="exit", shape=NodeShape.EXIT),
        ],
        edges=[
            Edge(source_id="start", target_id="work"),
            Edge(source_id="work", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[]),
    )
    dot_out = serializer.emit(pipeline)
    pipeline2 = serializer.parse(dot_out)
    work2 = next(n for n in pipeline2.nodes if n.node_id == "work")
    assert work2.prompt == 'Say "hello"'


def test_pydot_serializer_roundtrip_with_embedded_backslash_in_condition() -> None:
    """emit() -> parse() preserves edge condition values containing backslashes."""
    serializer = PydotSerializer()
    pipeline = Pipeline(
        spec_id="backslash_test",
        nodes=[
            Node(node_id="start", shape=NodeShape.START),
            Node(node_id="exit", shape=NodeShape.EXIT),
        ],
        edges=[
            Edge(source_id="start", target_id="exit", condition=r"path\to\value == 1"),
        ],
        stylesheet=Stylesheet(rules=[]),
    )
    dot_out = serializer.emit(pipeline)
    pipeline2 = serializer.parse(dot_out)
    edge2 = next(iter(pipeline2.edges))
    assert edge2.condition == r"path\to\value == 1"


# ---------------------------------------------------------------------------
# Stylesheet round-trip tests
# ---------------------------------------------------------------------------


def test_pydot_serializer_roundtrip_preserves_stylesheet_rules() -> None:
    """emit() -> parse() preserves non-empty stylesheet rules via graph attribute."""
    serializer = PydotSerializer()
    rules = [
        StyleRule(selector="*", profile="default"),
        StyleRule(selector="CODERGEN", profile="coder"),
        StyleRule(selector="#special", profile="vip"),
    ]
    pipeline = Pipeline(
        spec_id="ss_test",
        nodes=[
            Node(node_id="start", shape=NodeShape.START),
            Node(node_id="exit", shape=NodeShape.EXIT),
        ],
        edges=[Edge(source_id="start", target_id="exit")],
        stylesheet=Stylesheet(rules=rules),
    )
    dot_out = serializer.emit(pipeline)
    pipeline2 = serializer.parse(dot_out)
    assert pipeline2.stylesheet.rules == tuple(rules)


def test_pydot_serializer_roundtrip_empty_stylesheet_stays_empty() -> None:
    """emit() -> parse() with no stylesheet rules produces an empty Stylesheet."""
    serializer = PydotSerializer()
    pipeline = Pipeline(
        spec_id="empty_ss",
        nodes=[
            Node(node_id="start", shape=NodeShape.START),
            Node(node_id="exit", shape=NodeShape.EXIT),
        ],
        edges=[Edge(source_id="start", target_id="exit")],
        stylesheet=Stylesheet(rules=[]),
    )
    dot_out = serializer.emit(pipeline)
    pipeline2 = serializer.parse(dot_out)
    assert pipeline2.stylesheet.rules == ()


def test_pydot_serializer_roundtrip_preserves_stylesheet_with_special_chars() -> None:
    """emit() -> parse() preserves stylesheet rules with double-quotes in profile names."""
    serializer = PydotSerializer()
    rules = [StyleRule(selector=".worker", profile='say "hi"')]
    pipeline = Pipeline(
        spec_id="special_chars",
        nodes=[
            Node(node_id="start", shape=NodeShape.START),
            Node(node_id="exit", shape=NodeShape.EXIT),
        ],
        edges=[Edge(source_id="start", target_id="exit")],
        stylesheet=Stylesheet(rules=rules),
    )
    dot_out = serializer.emit(pipeline)
    pipeline2 = serializer.parse(dot_out)
    assert pipeline2.stylesheet.rules == tuple(rules)
