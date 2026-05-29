"""Comprehensive unit tests for pipeline validation edge cases (RED phase M6 US9).

All basic validation cases are covered by test_pipeline.py.
These tests focus on edge cases not yet covered:
  - launch_run rejects invalid pipelines before creating a run.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.exceptions import PipelineValidationError
from hermes_attractor.domain.pipeline import (
    Edge,
    Node,
    NodeShape,
    Pipeline,
    StyleRule,
    Stylesheet,
)
from hermes_attractor.use_cases.run_execution import launch_run

pytestmark = pytest.mark.unit

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _make_invalid_pipeline_no_start() -> Pipeline:
    """Build a pipeline with no START node (invalid)."""
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile="coder")
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    return Pipeline(
        spec_id="no-start",
        nodes=[work, exit_],
        edges=[Edge(source_id="work", target_id="exit")],
        stylesheet=Stylesheet(rules=[StyleRule(selector="*", profile="default")]),
    )


def test_launch_run_on_invalid_pipeline_raises_pipeline_validation_error() -> None:
    """launch_run with an invalid pipeline raises PipelineValidationError without creating a run.

    This test will FAIL because launch_run currently does not validate the pipeline.
    Once implemented, it should call pipeline.validate() and raise
    PipelineValidationError when issues are found.
    """
    pipeline = _make_invalid_pipeline_no_start()

    serializer = MagicMock()
    serializer.parse.return_value = pipeline

    store = MagicMock()
    store.load.return_value = "digraph no-start {}"

    run_state = MagicMock()
    kanban = MagicMock()
    clock = MagicMock()
    clock.now.return_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)

    with pytest.raises(PipelineValidationError):
        _ = launch_run(
            spec_id="no-start",
            initial_context={},
            kanban=kanban,
            run_state=run_state,
            serializer=serializer,
            store=store,
            clock=clock,
        )

    # No run should have been created in the store.
    run_state.create_run.assert_not_called()
