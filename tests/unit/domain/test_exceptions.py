"""Unit tests for the domain exception hierarchy."""

from __future__ import annotations

import pytest

from hermes_attractor.domain.exceptions import (
    AttractorError,
    DanglingEdgeError,
    PipelineValidationError,
    RunStateError,
    TraversalError,
    UnknownNodeError,
    UnknownProfileError,
    ValidationIssue,
)

pytestmark = pytest.mark.unit


def test_attractor_error_is_exception() -> None:
    """AttractorError must be a subclass of Exception."""
    assert issubclass(AttractorError, Exception)


def test_pipeline_validation_error_subclasses_attractor_error() -> None:
    """PipelineValidationError must subclass AttractorError."""
    assert issubclass(PipelineValidationError, AttractorError)


def test_unknown_node_error_subclasses_attractor_error() -> None:
    """UnknownNodeError must subclass AttractorError."""
    assert issubclass(UnknownNodeError, AttractorError)


def test_dangling_edge_error_subclasses_attractor_error() -> None:
    """DanglingEdgeError must subclass AttractorError."""
    assert issubclass(DanglingEdgeError, AttractorError)


def test_unknown_profile_error_subclasses_attractor_error() -> None:
    """UnknownProfileError must subclass AttractorError."""
    assert issubclass(UnknownProfileError, AttractorError)


def test_run_state_error_subclasses_attractor_error() -> None:
    """RunStateError must subclass AttractorError."""
    assert issubclass(RunStateError, AttractorError)


def test_traversal_error_subclasses_attractor_error() -> None:
    """TraversalError must subclass AttractorError."""
    assert issubclass(TraversalError, AttractorError)


def test_validation_issue_has_element_id_and_reason() -> None:
    """ValidationIssue must have element_id and reason attributes."""
    issue = ValidationIssue(element_id="node_1", reason="missing profile")
    assert issue.element_id == "node_1"
    assert issue.reason == "missing profile"


def test_pipeline_validation_error_accepts_validation_issues() -> None:
    """PipelineValidationError must accept a list of ValidationIssue objects."""
    issues = [
        ValidationIssue(element_id="node_1", reason="missing profile"),
        ValidationIssue(element_id="edge_2", reason="dangling source"),
    ]
    err = PipelineValidationError(issues=issues)
    assert err.issues == issues


def test_pipeline_validation_error_can_be_raised_and_caught() -> None:
    """PipelineValidationError must be raisable and catchable as AttractorError."""
    issues = [ValidationIssue(element_id="n", reason="bad")]
    err = PipelineValidationError(issues=issues, message="Pipeline validation failed")
    with pytest.raises(AttractorError):
        raise err
