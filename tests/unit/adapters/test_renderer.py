"""Unit tests for the Renderer port and pure-Python text adapter (RED phase for M1).

Tests fail until ports/renderer.py and adapters/renderer.py are implemented.
"""

from __future__ import annotations

import pytest

from hermes_attractor.adapters.renderer import TextRenderer
from hermes_attractor.domain.pipeline import Edge, Node, NodeShape, Pipeline, Stylesheet
from hermes_attractor.ports.renderer import Renderer

pytestmark = pytest.mark.unit

_PIPELINE = Pipeline(
    spec_id="test",
    nodes=[
        Node(node_id="start", shape=NodeShape.START),
        Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder"),
        Node(node_id="exit", shape=NodeShape.EXIT),
    ],
    edges=[
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="exit"),
    ],
    stylesheet=Stylesheet(rules=[]),
)


def test_renderer_protocol_has_summarize() -> None:
    """Renderer Protocol must declare a summarize method."""
    assert hasattr(Renderer, "summarize")
    assert callable(Renderer.summarize)


def test_text_renderer_summarize_returns_non_empty_string() -> None:
    """TextRenderer.summarize returns a non-empty string for any pipeline."""
    renderer = TextRenderer()
    summary = renderer.summarize(_PIPELINE)
    assert isinstance(summary, str)
    assert summary.strip(), "Summary must not be empty"


def test_text_renderer_summary_includes_node_ids() -> None:
    """TextRenderer.summarize includes all node_ids in the summary."""
    renderer = TextRenderer()
    summary = renderer.summarize(_PIPELINE)
    assert "start" in summary
    assert "work" in summary
    assert "exit" in summary


def test_text_renderer_summary_includes_node_shapes() -> None:
    """TextRenderer.summarize includes node shape information."""
    renderer = TextRenderer()
    summary = renderer.summarize(_PIPELINE)
    assert "START" in summary or "Mdiamond" in summary or "start" in summary.lower()


def test_text_renderer_summary_includes_edge_count() -> None:
    """TextRenderer.summarize includes the number of edges."""
    renderer = TextRenderer()
    summary = renderer.summarize(_PIPELINE)
    assert "2" in summary, "Summary should include the edge count (2 edges)"


def test_text_renderer_summary_includes_prompt_snippet() -> None:
    """TextRenderer.summarize includes a snippet of node prompts."""
    pipeline = Pipeline(
        spec_id="with_prompt",
        nodes=[
            Node(node_id="start", shape=NodeShape.START),
            Node(node_id="work", shape=NodeShape.CODERGEN, prompt="Do the important work now."),
            Node(node_id="exit", shape=NodeShape.EXIT),
        ],
        edges=[
            Edge(source_id="start", target_id="work"),
            Edge(source_id="work", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[]),
    )
    renderer = TextRenderer()
    summary = renderer.summarize(pipeline)
    assert "Do the important work now." in summary


def test_text_renderer_summary_truncates_long_prompt() -> None:
    """TextRenderer.summarize truncates long prompts to a snippet."""
    long_prompt = "A" * 50
    pipeline = Pipeline(
        spec_id="long_prompt",
        nodes=[
            Node(node_id="start", shape=NodeShape.START),
            Node(node_id="work", shape=NodeShape.CODERGEN, prompt=long_prompt),
            Node(node_id="exit", shape=NodeShape.EXIT),
        ],
        edges=[
            Edge(source_id="start", target_id="work"),
            Edge(source_id="work", target_id="exit"),
        ],
        stylesheet=Stylesheet(rules=[]),
    )
    renderer = TextRenderer()
    summary = renderer.summarize(pipeline)
    assert "..." in summary, "Long prompt should be truncated with '...'"


def test_text_renderer_summary_includes_edge_condition_and_label() -> None:
    """TextRenderer.summarize includes edge condition and label."""
    pipeline = Pipeline(
        spec_id="annotated_edges",
        nodes=[
            Node(node_id="start", shape=NodeShape.START),
            Node(node_id="exit", shape=NodeShape.EXIT),
        ],
        edges=[
            Edge(
                source_id="start",
                target_id="exit",
                condition='done == "yes"',
                label="success",
            ),
        ],
        stylesheet=Stylesheet(rules=[]),
    )
    renderer = TextRenderer()
    summary = renderer.summarize(pipeline)
    assert 'done == "yes"' in summary
    assert "success" in summary
