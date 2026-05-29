"""Domain exception hierarchy for hermes_attractor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class AttractorError(Exception):
    """Base class for all domain errors raised by hermes_attractor."""


class InvalidEchoError(AttractorError):
    """Raised when an echo message fails validation."""


@dataclass(frozen=True)
class ValidationIssue:
    """A single structured validation failure for a pipeline element.

    Attributes:
        element_id: The node_id or edge identifier that failed validation.
        reason: A human-readable description of why validation failed.
    """

    element_id: str
    reason: str


class PipelineValidationError(AttractorError):
    """Raised when pipeline validation fails; aggregates structured ValidationIssues.

    Prefer calling ``Pipeline.validate()`` (which returns issues rather than raising)
    and only raising this when a hard failure boundary is required (e.g. a tool handler
    receiving an invalid pipeline from the LLM).

    Attributes:
        issues: The list of ValidationIssue instances describing each failure.
    """

    def __init__(
        self,
        issues: Sequence[ValidationIssue],
        message: str = "Pipeline validation failed",
    ) -> None:
        """Initialise with a sequence of validation issues and an optional message.

        Args:
            issues: One or more ValidationIssue describing what failed.
            message: Human-readable summary; defaults to "Pipeline validation failed".
        """
        super().__init__(message)
        self.issues = list(issues)


class UnknownNodeError(AttractorError):
    """Raised when a referenced node_id does not exist in the pipeline (FR-004)."""


class DanglingEdgeError(AttractorError):
    """Raised when an edge references a node that does not exist (SC-007)."""


class UnknownProfileError(AttractorError):
    """Raised when a node names a profile not declared in the stylesheet (FR-019)."""


class RunStateError(AttractorError):
    """Raised on an illegal Run or RunNode state transition."""


class TraversalError(AttractorError):
    """Raised when traversal cannot continue (no selectable edge or inconsistent graph)."""
