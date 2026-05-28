"""Unit tests for the EchoMessage value object."""

from __future__ import annotations

import pytest

from hermes_attractor.domain.echo import EchoMessage
from hermes_attractor.domain.exceptions import InvalidEchoError

pytestmark = pytest.mark.unit


def test_accepts_non_empty_text() -> None:
    """A non-empty message is stored verbatim."""
    assert EchoMessage(value="hi").value == "hi"


def test_rejects_empty_string() -> None:
    """An empty message raises InvalidEchoError."""
    with pytest.raises(InvalidEchoError):
        _ = EchoMessage(value="")


def test_rejects_whitespace_only() -> None:
    """A whitespace-only message raises InvalidEchoError."""
    with pytest.raises(InvalidEchoError):
        _ = EchoMessage(value="   ")
