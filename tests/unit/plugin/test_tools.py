"""Unit tests for the Hermes tool handlers."""

from __future__ import annotations

import json

import pytest

from hermes_attractor.plugin.tools import handle_echo, handle_health

pytestmark = pytest.mark.unit


def test_handle_health_returns_ok_payload() -> None:
    """handle_health reports an ok status and a string version."""
    payload = json.loads(handle_health({}))
    assert payload["ok"] is True
    assert payload["result"]["status"] == "ok"
    assert isinstance(payload["result"]["version"], str)


def test_handle_echo_returns_message() -> None:
    """handle_echo echoes the provided message back."""
    payload = json.loads(handle_echo({"message": "ping"}))
    assert payload["ok"] is True
    assert payload["result"]["message"] == "ping"


def test_handle_echo_missing_message_returns_error() -> None:
    """handle_echo returns an error payload instead of raising on bad input."""
    payload = json.loads(handle_echo({}))
    assert payload["ok"] is False
    assert payload["error"] == "InvalidEchoError"
