"""Unit tests for the Hermes tool handlers."""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path  # noqa: TC003  # used in function signatures at runtime
from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.pipeline import (
    Context,
    Edge,
    Node,
    NodeShape,
    Pipeline,
    StyleRule,
    Stylesheet,
)
from hermes_attractor.domain.run import NodeRunStatus, Run, RunNode, RunStatus
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

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _make_pipeline(
    *,
    spec_id: str = "spec-a",
    node_profile: str = "coder",
    prompt: str = "Implement $task.",
) -> Pipeline:
    """Build a minimal Pipeline for a start -> work -> exit linear pipeline.

    Args:
        spec_id: Pipeline spec identifier.
        node_profile: The resolved profile for the work node.
        prompt: The work node's prompt template.

    Returns:
        A Pipeline instance.
    """
    start = Node(node_id="start", shape=NodeShape.START)
    work = Node(node_id="work", shape=NodeShape.CODERGEN, profile=node_profile, prompt=prompt)
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="work"),
        Edge(source_id="work", target_id="exit"),
    ]
    stylesheet = Stylesheet(rules=[StyleRule(selector="*", profile="default")])
    return Pipeline(
        spec_id=spec_id,
        nodes=[start, work, exit_],
        edges=edges,
        stylesheet=stylesheet,
    )


def _make_run(status: RunStatus = RunStatus.RUNNING) -> Run:
    """Build a minimal Run for testing.

    Args:
        status: The run's lifecycle status.

    Returns:
        A Run instance.
    """
    return Run(
        run_id="run1",
        spec_id="spec-a",
        status=status,
        context=Context(data={"task": "write tests"}),
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_run_node(
    node_id: str = "work",
    status: NodeRunStatus = NodeRunStatus.RUNNING,
    task_id: str = "task-001",
) -> RunNode:
    """Build a minimal RunNode for testing.

    Args:
        node_id: The pipeline node identifier.
        status: The node's current execution status.
        task_id: The kanban task identifier.

    Returns:
        A RunNode instance.
    """
    return RunNode(
        run_id="run1",
        node_id=node_id,
        task_id=task_id,
        status=status,
        attempt=1,
        parent_node_ids=[],
    )


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
        result = payload["result"]
        assert isinstance(result, dict)
        assert result["shape"] == "START"
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


def test_handle_attractor_set_stylesheet_ok(tmp_path: Path) -> None:
    """handle_attractor_set_stylesheet returns ok:true with spec_id and rules_count."""
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
        payload = _assert_json_response(response)
        assert payload["ok"] is True
        result = payload["result"]
        assert isinstance(result, dict)
        assert result["spec_id"] == "flow"
        assert result["rules_count"] == 1
    finally:
        if old_env is None:
            _ = os.environ.pop("ATTRACTOR_REPO_BASE", None)
        else:
            os.environ["ATTRACTOR_REPO_BASE"] = old_env


# ---------------------------------------------------------------------------
# Handler integration: happy-path JSON envelope tests (moved from use_cases).
# These verify the full call chain through the tool handler API.
# ---------------------------------------------------------------------------


def test_attractor_run_handler_returns_ok_json_with_run_id_and_status() -> None:
    """attractor_run tool handler returns {ok:true, result:{run_id, status}} JSON."""
    pipeline = _make_pipeline()
    kanban = MagicMock()
    kanban.create_card.return_value = "task-001"
    run_state = MagicMock()
    clock = MagicMock()
    clock.now.return_value = _NOW
    serializer = MagicMock()
    serializer.parse.return_value = pipeline
    store = MagicMock()
    store.load.return_value = "digraph spec-a {}"

    raw = handle_attractor_run(
        {"spec_id": "spec-a", "context": {"task": "write tests"}},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )

    payload = json.loads(raw)
    assert payload["ok"] is True
    assert "run_id" in payload["result"]
    assert "status" in payload["result"]


def test_attractor_status_handler_returns_ok_json_with_status_and_nodes() -> None:
    """attractor_status tool handler returns {run_id, status, current_nodes, context_keys} JSON."""
    run = _make_run()
    node = _make_run_node("work", NodeRunStatus.RUNNING, "task-001")
    run_state = MagicMock()
    run_state.get_run.return_value = run
    run_state.nodes_for_run.return_value = [node]

    raw = handle_attractor_status({"run_id": "run1"}, run_state=run_state)

    payload = json.loads(raw)
    assert payload["ok"] is True
    result = payload["result"]
    assert result["run_id"] == "run1"
    assert result["status"] == RunStatus.RUNNING.value
    assert "current_nodes" in result
    assert "context_keys" in result


def test_attractor_result_handler_returns_ok_json() -> None:
    """handle_attractor_result returns {ok:true, result:{run_id, status, outcome}} JSON."""
    run = _make_run(RunStatus.SUCCEEDED)
    run_state = MagicMock()
    run_state.get_run.return_value = run

    raw = handle_attractor_result({"run_id": "run1"}, run_state=run_state)

    payload = json.loads(raw)
    assert payload["ok"] is True
    result = payload["result"]
    assert result["run_id"] == "run1"
    assert result["status"] == RunStatus.SUCCEEDED.value
    assert "outcome" in result
