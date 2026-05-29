"""Integration tests for the authoring flow (create -> add_node -> add_edge -> validate).

These tests use real adapters (PydotSerializer, GitPipelineStore, TextRenderer) with tmp_path.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003  # used in function signatures at runtime
from unittest.mock import MagicMock

import pytest

from hermes_attractor.adapters.dot_serializer import PydotSerializer
from hermes_attractor.adapters.pipeline_store import GitPipelineStore
from hermes_attractor.adapters.renderer import TextRenderer
from hermes_attractor.domain.pipeline import NodeShape, StyleRule
from hermes_attractor.use_cases.authoring import (
    add_edge,
    add_node,
    create_graph,
    get_summary,
    remove_edge,
    remove_node,
    set_stylesheet,
    validate_pipeline,
)

pytestmark = pytest.mark.integration


def _make_adapters(tmp_path: Path) -> tuple[GitPipelineStore, PydotSerializer, TextRenderer]:
    """Build real adapters rooted in tmp_path.

    Args:
        tmp_path: Pytest tmp_path fixture.

    Returns:
        Tuple of (store, serializer, renderer).
    """
    store = GitPipelineStore(repo_root=tmp_path)
    store.ensure_repo()
    return store, PydotSerializer(), TextRenderer()


def test_create_graph_creates_pipeline(tmp_path: Path) -> None:
    """create_graph writes a .dot file to the store."""
    store, serializer, _renderer = _make_adapters(tmp_path)
    create_graph(spec_id="my_flow", store=store, serializer=serializer)
    assert (tmp_path / "my_flow.dot").exists()


def test_add_node_appends_node(tmp_path: Path) -> None:
    """add_node adds a node to the pipeline."""
    store, serializer, _renderer = _make_adapters(tmp_path)
    create_graph(spec_id="flow", store=store, serializer=serializer)
    updated = add_node(
        spec_id="flow",
        node_id="start",
        shape=NodeShape.START,
        store=store,
        serializer=serializer,
    )
    node_ids = {n.node_id for n in updated.nodes}
    assert "start" in node_ids


def test_add_edge_appends_edge(tmp_path: Path) -> None:
    """add_edge adds an edge to the pipeline."""
    store, serializer, _renderer = _make_adapters(tmp_path)
    create_graph(spec_id="flow", store=store, serializer=serializer)
    _ = add_node(spec_id="flow", node_id="start", shape=NodeShape.START, store=store, serializer=serializer)
    _ = add_node(spec_id="flow", node_id="exit", shape=NodeShape.EXIT, store=store, serializer=serializer)
    updated = add_edge(
        spec_id="flow",
        source_id="start",
        target_id="exit",
        store=store,
        serializer=serializer,
    )
    assert any(e.source_id == "start" and e.target_id == "exit" for e in updated.edges)


def test_remove_node_removes_node_and_edges(tmp_path: Path) -> None:
    """remove_node removes the node and all its connected edges."""
    store, serializer, _renderer = _make_adapters(tmp_path)
    create_graph(spec_id="flow", store=store, serializer=serializer)
    _ = add_node(spec_id="flow", node_id="start", shape=NodeShape.START, store=store, serializer=serializer)
    _ = add_node(
        spec_id="flow",
        node_id="work",
        shape=NodeShape.CODERGEN,
        profile="w",
        store=store,
        serializer=serializer,
    )
    _ = add_node(spec_id="flow", node_id="exit", shape=NodeShape.EXIT, store=store, serializer=serializer)
    _ = add_edge(spec_id="flow", source_id="start", target_id="work", store=store, serializer=serializer)
    _ = add_edge(spec_id="flow", source_id="work", target_id="exit", store=store, serializer=serializer)
    updated = remove_node(spec_id="flow", node_id="work", store=store, serializer=serializer)
    node_ids = {n.node_id for n in updated.nodes}
    assert "work" not in node_ids
    assert not any(e.source_id == "work" or e.target_id == "work" for e in updated.edges)


def test_remove_edge_removes_matching_edge(tmp_path: Path) -> None:
    """remove_edge removes the specified edge."""
    store, serializer, _renderer = _make_adapters(tmp_path)
    create_graph(spec_id="flow", store=store, serializer=serializer)
    _ = add_node(spec_id="flow", node_id="start", shape=NodeShape.START, store=store, serializer=serializer)
    _ = add_node(spec_id="flow", node_id="exit", shape=NodeShape.EXIT, store=store, serializer=serializer)
    _ = add_edge(spec_id="flow", source_id="start", target_id="exit", store=store, serializer=serializer)
    updated = remove_edge(
        spec_id="flow",
        source_id="start",
        target_id="exit",
        store=store,
        serializer=serializer,
    )
    assert not any(e.source_id == "start" and e.target_id == "exit" for e in updated.edges)


def test_set_stylesheet_updates_in_memory_pipeline(tmp_path: Path) -> None:
    """set_stylesheet applies stylesheet rules to the in-memory pipeline aggregate.

    Note: stylesheet rules are not currently persisted in DOT format (they are
    an in-memory overlay). This test verifies the in-memory effect. The store
    call uses a mock to avoid a git 'nothing to commit' failure.
    """
    serializer = PydotSerializer()
    pipeline = serializer.parse("digraph flow { start [shape=Mdiamond]; exit [shape=Msquare]; start -> exit; }")
    mock_store = MagicMock()
    mock_store.load.return_value = serializer.emit(pipeline)
    serializer2 = PydotSerializer()

    rules = [StyleRule(selector="*", profile="default-worker")]
    updated = set_stylesheet(spec_id="flow", rules=rules, store=mock_store, serializer=serializer2)
    assert updated.stylesheet.rules[0].profile == "default-worker"


def test_validate_pipeline_returns_valid_false_for_invalid_pipeline(tmp_path: Path) -> None:
    """validate_pipeline returns valid:false for a pipeline with missing start node."""
    store, serializer, _renderer = _make_adapters(tmp_path)
    create_graph(spec_id="flow", store=store, serializer=serializer)
    _ = add_node(
        spec_id="flow",
        node_id="work",
        shape=NodeShape.CODERGEN,
        profile="w",
        store=store,
        serializer=serializer,
    )
    result = validate_pipeline(spec_id="flow", store=store, serializer=serializer)
    assert result["valid"] is False


def test_get_summary_returns_summary_and_dot(tmp_path: Path) -> None:
    """get_summary returns a dict with summary and dot keys."""
    store, serializer, renderer = _make_adapters(tmp_path)
    create_graph(spec_id="flow", store=store, serializer=serializer)
    result = get_summary(spec_id="flow", store=store, serializer=serializer, renderer=renderer)
    assert "summary" in result
    assert "dot" in result
