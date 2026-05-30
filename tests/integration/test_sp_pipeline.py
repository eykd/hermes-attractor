"""Integration tests for the sp workflow DOT pipeline (M6 US8).

These tests exercise the real DOT parse path (PydotSerializer adapter + domain together)
and so live in the integration suite, not the domain unit suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_attractor.adapters.dot_serializer import PydotSerializer
from hermes_attractor.domain.pipeline import NodeShape, Pipeline

pytestmark = pytest.mark.integration

_SP_DOT_PATH = Path(__file__).parents[2] / "specs" / "pipelines" / "sp-workflow.dot"
_SERIALIZER = PydotSerializer()


def _load_pipeline() -> Pipeline:
    """Load and parse the sp-workflow.dot pipeline.

    Returns:
        The parsed Pipeline.
    """
    assert _SP_DOT_PATH.exists(), f"sp-workflow.dot not found at {_SP_DOT_PATH}"
    return _SERIALIZER.parse(_SP_DOT_PATH.read_text())


def test_sp_workflow_dot_file_exists() -> None:
    """specs/pipelines/sp-workflow.dot must exist."""
    assert _SP_DOT_PATH.exists(), f"sp-workflow.dot not found at {_SP_DOT_PATH}"


def test_sp_pipeline_validates_clean() -> None:
    """The sp-workflow.dot pipeline validates with no issues."""
    pipeline = _load_pipeline()
    issues = pipeline.validate()
    assert issues == [], f"Expected no validation issues, got: {issues}"


def test_sp_pipeline_has_fan_out_and_fan_in() -> None:
    """The sp pipeline has at least one FAN_OUT and one FAN_IN (parallel review lenses)."""
    pipeline = _load_pipeline()
    shapes = {n.shape for n in pipeline.nodes}
    assert NodeShape.FAN_OUT in shapes, "Expected at least one FAN_OUT node"
    assert NodeShape.FAN_IN in shapes, "Expected at least one FAN_IN node"


def test_sp_pipeline_has_human_node() -> None:
    """The sp pipeline has at least one HUMAN node (approval gate)."""
    pipeline = _load_pipeline()
    shapes = {n.shape for n in pipeline.nodes}
    assert NodeShape.HUMAN in shapes, "Expected at least one HUMAN node"


def test_sp_pipeline_has_gate_like_node() -> None:
    """The sp pipeline has at least one node with retry_limit > 0 (gate-like behavior).

    Note: GoalGatePolicy is not yet parseable from DOT attributes. We verify
    the presence of gate-like semantics via retry_limit > 0, which is the
    DOT-serializable proxy for gate configuration.
    """
    pipeline = _load_pipeline()
    gate_like = [n for n in pipeline.nodes if n.retry_limit > 0]
    assert gate_like, "Expected at least one node with retry_limit > 0 (gate-like)"


def test_sp_pipeline_has_tool_node() -> None:
    """The sp pipeline has at least one TOOL node."""
    pipeline = _load_pipeline()
    shapes = {n.shape for n in pipeline.nodes}
    assert NodeShape.TOOL in shapes, "Expected at least one TOOL node"


def test_sp_pipeline_has_multiple_distinct_profiles() -> None:
    """The sp pipeline uses at least 2 distinct profiles (per-node profile variety)."""
    pipeline = _load_pipeline()
    profiles: set[str | None] = {
        pipeline.resolve_profile(n) for n in pipeline.nodes if n.profile or pipeline.stylesheet.resolve(n)
    }
    assert len(profiles) >= 2, f"Expected at least 2 distinct profiles, got: {profiles}"
