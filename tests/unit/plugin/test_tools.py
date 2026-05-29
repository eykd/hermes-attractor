"""Unit tests for the Hermes tool handlers."""

from __future__ import annotations

import json

import pytest

from hermes_attractor.plugin.tools import (
    handle_attractor_add_edge,
    handle_attractor_add_node,
    handle_attractor_create_graph,
    handle_attractor_remove_edge,
    handle_attractor_remove_node,
    handle_attractor_set_stylesheet,
    handle_attractor_summary,
    handle_attractor_validate,
    handle_echo,
    handle_health,
)

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


# ---------------------------------------------------------------------------
# Stub authoring handlers (M1 — not yet implemented, return ok:false).
# These tests verify the stubs are importable, honor the never-raise contract,
# and return a structured not-implemented error payload.
# ---------------------------------------------------------------------------


def _assert_not_implemented(response: str, tool_name: str) -> None:
    """Assert that a stub handler returns a well-formed not-implemented error payload."""
    payload = json.loads(response)
    assert payload["ok"] is False
    assert payload["error"] == "NotImplementedError"
    assert tool_name in payload["message"]


def test_handle_attractor_create_graph_is_stub() -> None:
    """handle_attractor_create_graph returns a not-implemented payload (M1 stub)."""
    _assert_not_implemented(handle_attractor_create_graph({"spec_id": "x"}), "attractor_create_graph")


def test_handle_attractor_add_node_is_stub() -> None:
    """handle_attractor_add_node returns a not-implemented payload (M1 stub)."""
    _assert_not_implemented(
        handle_attractor_add_node({"spec_id": "x", "node_id": "n", "shape": "START"}),
        "attractor_add_node",
    )


def test_handle_attractor_remove_node_is_stub() -> None:
    """handle_attractor_remove_node returns a not-implemented payload (M1 stub)."""
    _assert_not_implemented(
        handle_attractor_remove_node({"spec_id": "x", "node_id": "n"}),
        "attractor_remove_node",
    )


def test_handle_attractor_add_edge_is_stub() -> None:
    """handle_attractor_add_edge returns a not-implemented payload (M1 stub)."""
    _assert_not_implemented(
        handle_attractor_add_edge({"spec_id": "x", "source_id": "a", "target_id": "b"}),
        "attractor_add_edge",
    )


def test_handle_attractor_remove_edge_is_stub() -> None:
    """handle_attractor_remove_edge returns a not-implemented payload (M1 stub)."""
    _assert_not_implemented(
        handle_attractor_remove_edge({"spec_id": "x", "source_id": "a", "target_id": "b"}),
        "attractor_remove_edge",
    )


def test_handle_attractor_set_stylesheet_is_stub() -> None:
    """handle_attractor_set_stylesheet returns a not-implemented payload (M1 stub)."""
    _assert_not_implemented(
        handle_attractor_set_stylesheet({"spec_id": "x", "rules": []}),
        "attractor_set_stylesheet",
    )


def test_handle_attractor_validate_is_stub() -> None:
    """handle_attractor_validate returns a not-implemented payload (M1 stub)."""
    _assert_not_implemented(handle_attractor_validate({"spec_id": "x"}), "attractor_validate")


def test_handle_attractor_summary_is_stub() -> None:
    """handle_attractor_summary returns a not-implemented payload (M1 stub)."""
    _assert_not_implemented(handle_attractor_summary({"spec_id": "x"}), "attractor_summary")
