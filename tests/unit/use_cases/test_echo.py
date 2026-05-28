"""Unit tests for the echo use case."""

from __future__ import annotations

import pytest

from hermes_attractor.domain.exceptions import InvalidEchoError
from hermes_attractor.use_cases.echo import echo

pytestmark = pytest.mark.unit


def test_echo_wraps_message() -> None:
    """Wrap the supplied text in an EchoMessage."""
    assert echo("hello").value == "hello"


def test_echo_rejects_empty() -> None:
    """Raise InvalidEchoError for an empty message."""
    with pytest.raises(InvalidEchoError):
        _ = echo("")
