"""Domain exception hierarchy for hermes_attractor."""

from __future__ import annotations


class AttractorError(Exception):
    """Base class for all domain errors raised by hermes_attractor."""


class InvalidEchoError(AttractorError):
    """Raised when an echo message fails validation."""
