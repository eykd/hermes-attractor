"""Unit tests for authoring use cases (RED phase for M1).

Tests fail until src/hermes_attractor/use_cases/authoring.py is implemented.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.pipeline import (
    Edge,
    Node,
    NodeShape,
    Pipeline,
    StyleRule,
    Stylesheet,
)
from hermes_attractor.use_cases.authoring import (
    add_edge,
    add_node,
    create_graph,
    get_summary,
    set_stylesheet,
    validate_pipeline,
)

pytestmark = pytest.mark.unit

_EMPTY_DOT = "digraph spec { }"
_VALID_DOT = "digraph spec { start [shape=Mdiamond]; exit [shape=Msquare]; start -> exit; }"


def _make_mocks(dot_content: str = _VALID_DOT) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Create mock store, serializer, and renderer for authoring tests.

    Returns:
        A tuple of (store, serializer, renderer) mocks.
    """
    store = MagicMock()
    store.load.return_value = dot_content

    pipeline = Pipeline(
        spec_id="spec",
        nodes=[
            Node(node_id="start", shape=NodeShape.START),
            Node(node_id="exit", shape=NodeShape.EXIT),
        ],
        edges=[Edge(source_id="start", target_id="exit")],
        stylesheet=Stylesheet(rules=[]),
    )
    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    serializer.emit.return_value = _VALID_DOT

    renderer = MagicMock()
    renderer.summarize.return_value = "Pipeline: spec\n  Nodes: 2\n  Edges: 1"

    return store, serializer, renderer


def test_create_graph_saves_empty_pipeline(tmp_path: object) -> None:
    """create_graph saves a new empty pipeline via the store."""
    store = MagicMock()
    serializer = MagicMock()
    serializer.emit.return_value = _EMPTY_DOT
    create_graph(spec_id="new_spec", store=store, serializer=serializer)
    store.save.assert_called_once()


def test_add_node_loads_adds_and_saves() -> None:
    """add_node loads the pipeline, adds a node, and saves the updated DOT."""
    store, serializer, _renderer = _make_mocks()
    _ = add_node(
        spec_id="spec",
        node_id="work",
        shape=NodeShape.CODERGEN,
        store=store,
        serializer=serializer,
    )
    store.load.assert_called_once_with("spec")
    store.save.assert_called_once()


def test_add_edge_loads_adds_and_saves() -> None:
    """add_edge loads the pipeline, adds an edge, and saves the updated DOT."""
    store, serializer, _renderer = _make_mocks()
    _ = add_edge(
        spec_id="spec",
        source_id="start",
        target_id="exit",
        store=store,
        serializer=serializer,
    )
    store.load.assert_called_once_with("spec")
    store.save.assert_called_once()


def test_set_stylesheet_loads_and_saves() -> None:
    """set_stylesheet loads the pipeline, applies stylesheet rules, and saves."""
    store, serializer, _renderer = _make_mocks()
    rules = [StyleRule(selector="*", profile="default")]
    _ = set_stylesheet(spec_id="spec", rules=rules, store=store, serializer=serializer)
    store.load.assert_called_once_with("spec")
    store.save.assert_called_once()


def test_validate_pipeline_returns_valid_true_for_valid_pipeline() -> None:
    """validate_pipeline returns {valid: True, issues: []} for a valid pipeline."""
    store, serializer, _renderer = _make_mocks()
    result = validate_pipeline(spec_id="spec", store=store, serializer=serializer)
    assert result["valid"] is True
    assert result["issues"] == []


def test_get_summary_returns_summary_and_dot() -> None:
    """get_summary returns a dict with summary and dot keys."""
    store, serializer, renderer = _make_mocks()
    result = get_summary(spec_id="spec", store=store, serializer=serializer, renderer=renderer)
    assert "summary" in result
    assert "dot" in result
    assert isinstance(result["summary"], str)
    assert isinstance(result["dot"], str)
