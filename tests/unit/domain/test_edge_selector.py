"""Unit tests for the EdgeSelector domain service (RED phase for M1).

Tests fail until src/hermes_attractor/domain/edge_selector.py is implemented.
"""

from __future__ import annotations

import pytest

from hermes_attractor.domain.edge_selector import select
from hermes_attractor.domain.pipeline import Edge

pytestmark = pytest.mark.unit


def test_select_higher_weight_wins() -> None:
    """Given two edges with weights 1 and 2, select() returns the higher-weight edge."""
    edges = [
        Edge(source_id="a", target_id="low", weight=1),
        Edge(source_id="a", target_id="high", weight=2),
    ]
    selected = select(edges, context={}, routing_hint=None, suggested_nodes=[])
    assert selected is not None
    assert selected.target_id == "high"


def test_select_matching_condition_beats_higher_weight() -> None:
    """An edge with a matching condition wins over a non-matching higher-weight edge."""
    edges = [
        Edge(source_id="a", target_id="conditional", condition='status == "done"', weight=0),
        Edge(source_id="a", target_id="default", weight=10),
    ]
    selected = select(edges, context={"status": "done"}, routing_hint=None, suggested_nodes=[])
    assert selected is not None
    assert selected.target_id == "conditional"


def test_select_non_matching_condition_excluded() -> None:
    """An edge whose condition evaluates to False is not selected."""
    edges = [
        Edge(source_id="a", target_id="conditional", condition='status == "done"', weight=10),
        Edge(source_id="a", target_id="fallback", weight=0),
    ]
    selected = select(edges, context={"status": "pending"}, routing_hint=None, suggested_nodes=[])
    assert selected is not None
    assert selected.target_id == "fallback"


def test_select_lexical_tiebreak_on_target_id() -> None:
    """When all else is equal, the edge with the lexically smallest target_id is selected."""
    edges = [
        Edge(source_id="a", target_id="z_target", weight=0),
        Edge(source_id="a", target_id="a_target", weight=0),
    ]
    selected = select(edges, context={}, routing_hint=None, suggested_nodes=[])
    assert selected is not None
    assert selected.target_id == "a_target"


def test_select_routing_hint_label_wins_over_weight() -> None:
    """An edge whose label matches the routing_hint wins over a higher-weight edge."""
    edges = [
        Edge(source_id="a", target_id="labeled", label="yes", weight=0),
        Edge(source_id="a", target_id="heavy", weight=100),
    ]
    selected = select(edges, context={}, routing_hint="yes", suggested_nodes=[])
    assert selected is not None
    assert selected.target_id == "labeled"


def test_select_returns_none_for_empty_candidates() -> None:
    """select() returns None when there are no candidate edges."""
    selected = select([], context={}, routing_hint=None, suggested_nodes=[])
    assert selected is None


def test_select_suggested_node_wins_over_weight() -> None:
    """An edge to a suggested node wins over a higher-weight non-suggested edge."""
    edges = [
        Edge(source_id="a", target_id="suggested", weight=0),
        Edge(source_id="a", target_id="heavy", weight=100),
    ]
    selected = select(edges, context={}, routing_hint=None, suggested_nodes=["suggested"])
    assert selected is not None
    assert selected.target_id == "suggested"


def test_select_returns_none_when_all_conditions_fail() -> None:
    """select() returns None when all edges have failing conditions."""
    edges = [
        Edge(source_id="a", target_id="x", condition='status == "done"'),
        Edge(source_id="a", target_id="y", condition='status == "complete"'),
    ]
    selected = select(edges, context={"status": "pending"}, routing_hint=None, suggested_nodes=[])
    assert selected is None
