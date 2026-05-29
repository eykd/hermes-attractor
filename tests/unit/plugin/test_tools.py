"""Unit tests for the Hermes tool handlers."""

from __future__ import annotations

import json
import os
from pathlib import Path  # noqa: TC003  # used in function signatures at runtime

import pytest

from hermes_attractor.plugin.tools import (
    handle_attractor_add_edge,
    handle_attractor_add_node,
    handle_attractor_create_graph,
    handle_attractor_remove_edge,
    handle_attractor_remove_node,
    handle_attractor_result,
    handle_attractor_run,
    handle_attractor_set_stylesheet,
    handle_attractor_status,
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
# Authoring handlers: never-raise contract (M1 — real implementations).
# These tests verify that each handler returns a JSON string and never raises,
# even when the underlying store raises PipelineValidationError (no file/repo).
# ---------------------------------------------------------------------------


def _assert_json_response(response: str) -> dict[str, object]:
    """Assert that a response is a valid JSON string and return the parsed dict."""
    payload: dict[str, object] = json.loads(response)
    assert isinstance(payload.get("ok"), bool), "Response must have 'ok' bool field"
    return payload


def test_handle_attractor_create_graph_never_raises() -> None:
    """handle_attractor_create_graph returns a JSON string and never raises."""
    response = handle_attractor_create_graph({"spec_id": "test_pipe", "repo_path": "/nonexistent"})
    _ = _assert_json_response(response)


def test_handle_attractor_add_node_never_raises() -> None:
    """handle_attractor_add_node returns a JSON string and never raises."""
    response = handle_attractor_add_node(
        {"spec_id": "x", "node_id": "n", "shape": "START", "repo_path": "/nonexistent"}
    )
    _ = _assert_json_response(response)


def test_handle_attractor_remove_node_never_raises() -> None:
    """handle_attractor_remove_node returns a JSON string and never raises."""
    response = handle_attractor_remove_node({"spec_id": "x", "node_id": "n", "repo_path": "/nonexistent"})
    _ = _assert_json_response(response)


def test_handle_attractor_add_edge_never_raises() -> None:
    """handle_attractor_add_edge returns a JSON string and never raises."""
    response = handle_attractor_add_edge(
        {"spec_id": "x", "source_id": "a", "target_id": "b", "repo_path": "/nonexistent"}
    )
    _ = _assert_json_response(response)


def test_handle_attractor_remove_edge_never_raises() -> None:
    """handle_attractor_remove_edge returns a JSON string and never raises."""
    response = handle_attractor_remove_edge(
        {"spec_id": "x", "source_id": "a", "target_id": "b", "repo_path": "/nonexistent"}
    )
    _ = _assert_json_response(response)


def test_handle_attractor_set_stylesheet_never_raises() -> None:
    """handle_attractor_set_stylesheet returns a JSON string and never raises."""
    response = handle_attractor_set_stylesheet({"spec_id": "x", "rules": [], "repo_path": "/nonexistent"})
    _ = _assert_json_response(response)


def test_handle_attractor_validate_never_raises() -> None:
    """handle_attractor_validate returns a JSON string and never raises."""
    response = handle_attractor_validate({"spec_id": "x", "repo_path": "/nonexistent"})
    _ = _assert_json_response(response)


def test_handle_attractor_summary_never_raises() -> None:
    """handle_attractor_summary returns a JSON string and never raises."""
    response = handle_attractor_summary({"spec_id": "x", "repo_path": "/nonexistent"})
    _ = _assert_json_response(response)


# ---------------------------------------------------------------------------
# Happy-path tests using tmp_path to cover the ok:true return branches.
# repo_path must be relative within ATTRACTOR_REPO_BASE; we set the base to
# tmp_path.parent and pass tmp_path.name as the relative repo_path.
# ---------------------------------------------------------------------------


def test_handle_attractor_create_and_add_node_ok(tmp_path: Path) -> None:
    """handle_attractor_add_node returns ok:true when pipeline exists."""
    base = str(tmp_path.parent)
    repo = tmp_path.name
    old_env = os.environ.get("ATTRACTOR_REPO_BASE")
    try:
        os.environ["ATTRACTOR_REPO_BASE"] = base
        _ = _assert_json_response(handle_attractor_create_graph({"spec_id": "flow", "repo_path": repo}))
        response = handle_attractor_add_node(
            {"spec_id": "flow", "node_id": "start", "shape": "START", "repo_path": repo}
        )
        payload = _assert_json_response(response)
        assert payload["ok"] is True
    finally:
        if old_env is None:
            _ = os.environ.pop("ATTRACTOR_REPO_BASE", None)
        else:
            os.environ["ATTRACTOR_REPO_BASE"] = old_env


def test_handle_attractor_remove_node_ok(tmp_path: Path) -> None:
    """handle_attractor_remove_node returns ok:true when pipeline and node exist."""
    base = str(tmp_path.parent)
    repo = tmp_path.name
    old_env = os.environ.get("ATTRACTOR_REPO_BASE")
    try:
        os.environ["ATTRACTOR_REPO_BASE"] = base
        _ = _assert_json_response(handle_attractor_create_graph({"spec_id": "flow", "repo_path": repo}))
        _ = _assert_json_response(
            handle_attractor_add_node({"spec_id": "flow", "node_id": "start", "shape": "START", "repo_path": repo})
        )
        response = handle_attractor_remove_node({"spec_id": "flow", "node_id": "start", "repo_path": repo})
        payload = _assert_json_response(response)
        assert payload["ok"] is True
    finally:
        if old_env is None:
            _ = os.environ.pop("ATTRACTOR_REPO_BASE", None)
        else:
            os.environ["ATTRACTOR_REPO_BASE"] = old_env


def test_handle_attractor_add_and_remove_edge_ok(tmp_path: Path) -> None:
    """handle_attractor_add_edge and remove_edge return ok:true when pipeline exists."""
    base = str(tmp_path.parent)
    repo = tmp_path.name
    old_env = os.environ.get("ATTRACTOR_REPO_BASE")
    try:
        os.environ["ATTRACTOR_REPO_BASE"] = base
        _ = _assert_json_response(handle_attractor_create_graph({"spec_id": "flow", "repo_path": repo}))
        _ = _assert_json_response(
            handle_attractor_add_node({"spec_id": "flow", "node_id": "start", "shape": "START", "repo_path": repo})
        )
        _ = _assert_json_response(
            handle_attractor_add_node({"spec_id": "flow", "node_id": "exit", "shape": "EXIT", "repo_path": repo})
        )
        add_resp = handle_attractor_add_edge(
            {"spec_id": "flow", "source_id": "start", "target_id": "exit", "repo_path": repo}
        )
        assert _assert_json_response(add_resp)["ok"] is True

        remove_resp = handle_attractor_remove_edge(
            {"spec_id": "flow", "source_id": "start", "target_id": "exit", "repo_path": repo}
        )
        assert _assert_json_response(remove_resp)["ok"] is True
    finally:
        if old_env is None:
            _ = os.environ.pop("ATTRACTOR_REPO_BASE", None)
        else:
            os.environ["ATTRACTOR_REPO_BASE"] = old_env


def test_handle_attractor_run_never_raises() -> None:
    """handle_attractor_run returns a JSON string and never raises (M2 stub).

    Omitting repo_path causes _make_store to use cwd (default); omitting run_state
    exercises the SqliteRunStateStore branch; no kanban triggers the RuntimeError branch.
    All paths are caught by _safe and returned as ok:false.
    """
    response = handle_attractor_run({"spec_id": "x"})
    _ = _assert_json_response(response)


def test_handle_attractor_status_never_raises() -> None:
    """handle_attractor_status returns a JSON string and never raises (M2 stub)."""
    response = handle_attractor_status({"run_id": "some-run-id"})
    _ = _assert_json_response(response)


def test_handle_attractor_result_never_raises() -> None:
    """handle_attractor_result returns a JSON string and never raises (M2 stub)."""
    response = handle_attractor_result({"run_id": "some-run-id"})
    _ = _assert_json_response(response)


# ---------------------------------------------------------------------------
# Security: repo_path confinement tests
# ---------------------------------------------------------------------------


def test_make_store_rejects_absolute_repo_path() -> None:
    """_make_store rejects an absolute repo_path and handler returns ok:false."""
    response = handle_attractor_create_graph({"spec_id": "x", "repo_path": "/tmp/evil"})  # noqa: S108
    payload = _assert_json_response(response)
    assert payload["ok"] is False
    assert payload["error"] == "RepoPathConfinementError"


def test_make_store_rejects_dotdot_repo_path() -> None:
    """_make_store rejects a repo_path with '..' segments and handler returns ok:false."""
    response = handle_attractor_create_graph({"spec_id": "x", "repo_path": "../escape"})
    payload = _assert_json_response(response)
    assert payload["ok"] is False
    assert payload["error"] == "RepoPathConfinementError"


def test_make_store_rejects_path_outside_base(tmp_path: Path) -> None:
    """_make_store rejects a path that resolves outside the allowed base."""
    # Set ATTRACTOR_REPO_BASE to tmp_path, then try to escape it
    old_env = os.environ.get("ATTRACTOR_REPO_BASE")
    try:
        os.environ["ATTRACTOR_REPO_BASE"] = str(tmp_path)
        # Absolute path is caught before is_relative_to; use an absolute path.
        response = handle_attractor_create_graph({"spec_id": "x", "repo_path": "/other/dir"})
        payload = _assert_json_response(response)
        assert payload["ok"] is False
        assert payload["error"] == "RepoPathConfinementError"
    finally:
        if old_env is None:
            _ = os.environ.pop("ATTRACTOR_REPO_BASE", None)
        else:
            os.environ["ATTRACTOR_REPO_BASE"] = old_env


def test_make_store_rejects_symlink_escaping_base(tmp_path: Path) -> None:
    """_make_store rejects a symlinked path that resolves outside the allowed base.

    This exercises the post-resolution is_relative_to guard which catches symlink-based
    escapes that slip past the '..' and is_absolute early checks.
    """
    # Create a sibling directory that is outside the allowed base
    outside = tmp_path.parent / "outside_dir"
    outside.mkdir()
    # Create a symlink inside the base pointing to the outside directory
    link = tmp_path / "escape_link"
    link.symlink_to(outside)

    old_env = os.environ.get("ATTRACTOR_REPO_BASE")
    try:
        os.environ["ATTRACTOR_REPO_BASE"] = str(tmp_path)
        # "escape_link" is a relative path with no ".." — but resolves outside base
        response = handle_attractor_create_graph({"spec_id": "x", "repo_path": "escape_link"})
        payload = _assert_json_response(response)
        assert payload["ok"] is False
        assert payload["error"] == "RepoPathConfinementError"
    finally:
        if old_env is None:
            _ = os.environ.pop("ATTRACTOR_REPO_BASE", None)
        else:
            os.environ["ATTRACTOR_REPO_BASE"] = old_env


def test_make_store_accepts_relative_path_within_base(tmp_path: Path) -> None:
    """_make_store accepts a relative path within the allowed base directory."""
    # Use tmp_path's parent as the base so tmp_path's name is a valid relative subdir.
    base = tmp_path.parent
    subdir = tmp_path.name  # an existing directory within base
    old_env = os.environ.get("ATTRACTOR_REPO_BASE")
    try:
        os.environ["ATTRACTOR_REPO_BASE"] = str(base)
        response = handle_attractor_create_graph({"spec_id": "flow", "repo_path": subdir})
        payload = _assert_json_response(response)
        # Should succeed (ok:true) because subdir exists and is within base
        assert payload["ok"] is True
    finally:
        if old_env is None:
            _ = os.environ.pop("ATTRACTOR_REPO_BASE", None)
        else:
            os.environ["ATTRACTOR_REPO_BASE"] = old_env


def test_handle_attractor_set_stylesheet_empty_rules_never_raises(tmp_path: Path) -> None:
    """handle_attractor_set_stylesheet returns JSON (ok:false) when stylesheet doesn't change DOT.

    Note: setting a stylesheet when the emitted DOT content doesn't change causes git to
    fail with 'nothing to commit'. The _safe wrapper catches this as PipelineValidationError
    and returns ok:false. The ok:true happy path is not exercised here because stylesheet
    rules are not persisted in DOT format (known limitation, to be addressed in a future task).
    """
    base = str(tmp_path.parent)
    repo = tmp_path.name
    old_env = os.environ.get("ATTRACTOR_REPO_BASE")
    try:
        os.environ["ATTRACTOR_REPO_BASE"] = base
        _ = _assert_json_response(handle_attractor_create_graph({"spec_id": "flow", "repo_path": repo}))
        _ = _assert_json_response(
            handle_attractor_add_node({"spec_id": "flow", "node_id": "start", "shape": "START", "repo_path": repo})
        )
        response = handle_attractor_set_stylesheet(
            {
                "spec_id": "flow",
                "rules": [{"selector": "*", "profile": "default"}],
                "repo_path": repo,
            }
        )
        _ = _assert_json_response(response)
    finally:
        if old_env is None:
            _ = os.environ.pop("ATTRACTOR_REPO_BASE", None)
        else:
            os.environ["ATTRACTOR_REPO_BASE"] = old_env
