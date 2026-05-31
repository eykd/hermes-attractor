"""In-process end-to-end reconcile test against the REAL hermes-agent kanban backend.

This is the durable proof for zym.31 Part B: it authors a tiny linear pipeline, launches a
run (creating the first card via the real ``kanban_create`` tool), simulates a worker
completing that card via the real ``kanban_complete`` tool (no LLM, no model key), runs the
reconcile loop, and asserts the run advanced and the next card was created — all against a
real ``~/.hermes`` kanban SQLite DB isolated to ``tmp_path``.

``hermes-agent`` is in the ``test`` dependency-group, so this runs as part of the default
``uv run pytest`` (and ``just test-hermes`` for just the integration subset). The
``pytest.importorskip`` guards remain as a graceful fallback if that group is absent.

Hermetic and repeatable: a fresh temp ``HERMES_HOME`` + kanban DB per run (see
``conftest.py``), so re-running yields the same green result.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("hermes_cli.kanban_db")
pytest.importorskip("tools.registry")

from hermes_attractor.adapters.dot_serializer import PydotSerializer
from hermes_attractor.adapters.pipeline_store import GitPipelineStore
from hermes_attractor.adapters.run_state_store import SqliteRunStateStore
from hermes_attractor.adapters.system_clock import SystemClock
from hermes_attractor.domain.pipeline import NodeShape
from hermes_attractor.domain.run import NodeRunStatus, RunStatus
from hermes_attractor.plugin import reconcile
from hermes_attractor.plugin.reconcile import run_reconcile
from hermes_attractor.plugin.tools import handle_attractor_run
from hermes_attractor.use_cases.authoring import add_edge, add_node, create_graph
from hermes_attractor.use_cases.run_execution import launch_run

if TYPE_CHECKING:
    from hermes_attractor.adapters.kanban_board import HermesKanbanBoard
    from hermes_attractor.adapters.runtime_tool_client import RuntimeToolClient
    from hermes_attractor.adapters.task_event_reader import SqliteTaskEventReader
    from hermes_attractor.domain.run import RunNode

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Reusable helpers (small + parametrizable so gate/fan-out shapes can reuse them)
# ---------------------------------------------------------------------------


def _author_linear_pipeline(store: GitPipelineStore, serializer: PydotSerializer, spec_id: str) -> None:
    """Author a START -> node_a -> node_b -> EXIT pipeline via the authoring use cases.

    Args:
        store: The pipeline store to persist into.
        serializer: The DOT serializer.
        spec_id: The pipeline identifier.
    """
    create_graph(spec_id=spec_id, store=store, serializer=serializer)
    add_node(spec_id=spec_id, node_id="start", shape=NodeShape.START, store=store, serializer=serializer)
    add_node(
        spec_id=spec_id,
        node_id="node_a",
        shape=NodeShape.CODERGEN,
        prompt="Do step A.",
        profile="coder",
        store=store,
        serializer=serializer,
    )
    add_node(
        spec_id=spec_id,
        node_id="node_b",
        shape=NodeShape.CODERGEN,
        prompt="Do step B.",
        profile="coder",
        store=store,
        serializer=serializer,
    )
    add_node(spec_id=spec_id, node_id="exit", shape=NodeShape.EXIT, store=store, serializer=serializer)
    add_edge(spec_id=spec_id, source_id="start", target_id="node_a", store=store, serializer=serializer)
    add_edge(spec_id=spec_id, source_id="node_a", target_id="node_b", store=store, serializer=serializer)
    add_edge(spec_id=spec_id, source_id="node_b", target_id="exit", store=store, serializer=serializer)


def _latest_node(run_state: SqliteRunStateStore, run_id: str, node_id: str) -> RunNode | None:
    """Return the highest-attempt RunNode for ``node_id`` in ``run_id`` (or None).

    Args:
        run_state: The run-state store to query.
        run_id: The run identifier.
        node_id: The pipeline node identifier.

    Returns:
        The latest RunNode for the node, or None if not yet dispatched.
    """
    matching = [n for n in run_state.nodes_for_run(run_id) if n.node_id == node_id]
    if not matching:
        return None
    return max(matching, key=lambda n: n.attempt)


def _kanban_task_status(task_id: str) -> str | None:
    """Return the kanban task's status, or None if it does not exist.

    Args:
        task_id: The kanban task id to look up.

    Returns:
        The task status string, or None if the task is absent.
    """
    kanban_db = importlib.import_module("hermes_cli.kanban_db")
    conn = kanban_db.connect()
    try:
        task = kanban_db.get_task(conn, task_id)
    finally:
        conn.close()
    return None if task is None else str(task.status)


def _complete(tool_client: RuntimeToolClient, task_id: str, *, summary: str, metadata: dict[str, object]) -> None:
    """Simulate a worker completing a card via the real kanban_complete tool.

    Args:
        tool_client: The runtime tool client.
        task_id: The kanban task to complete.
        summary: The completion summary.
        metadata: Structured completion metadata (gate verdict / context updates).
    """
    response = tool_client.call("kanban_complete", task_id=task_id, summary=summary, metadata=metadata)
    assert isinstance(response, dict)
    assert response.get("ok") is True, response


# ---------------------------------------------------------------------------
# The reconcile loop, end-to-end
# ---------------------------------------------------------------------------


def test_reconcile_advances_linear_run_against_real_kanban(
    hermes_home: Path,  # fixture sets up isolated env
    kanban: HermesKanbanBoard,
    tool_client: RuntimeToolClient,
    event_reader: SqliteTaskEventReader,
) -> None:
    """Launch -> complete node_a -> reconcile advances the run and creates node_b's card."""
    serializer = PydotSerializer()
    store = GitPipelineStore.from_env(None)
    run_state = SqliteRunStateStore(db_path=Path(os.environ["ATTRACTOR_DB_PATH"]))
    clock = SystemClock()
    spec_id = "reconcile_e2e"
    _author_linear_pipeline(store, serializer, spec_id)

    launched = launch_run(
        spec_id=spec_id,
        initial_context={},
        kanban=kanban,
        run_state=run_state,
        serializer=serializer,
        store=store,
        clock=clock,
    )
    run_id = str(launched["run_id"])

    # launch_run created node_a's card via the real kanban_create tool.
    node_a = _latest_node(run_state, run_id, "node_a")
    assert node_a is not None
    assert node_a.task_id
    assert _kanban_task_status(node_a.task_id) is not None, "node_a task must exist in the real kanban DB"
    assert _latest_node(run_state, run_id, "node_b") is None, "node_b must not exist before reconcile"

    # Simulate the worker completing node_a (writes a terminal task_events row + run metadata).
    _complete(tool_client, node_a.task_id, summary="A done", metadata={"context_updates": {"a": "done"}})

    # Reconcile using env-default stores (exactly what the on_session_start hook builds).
    run_reconcile(tool_client=tool_client, event_reader=event_reader)

    # The reconciler read the completion, advanced the run, and created node_b's card.
    run = run_state.get_run(run_id)
    assert run is not None
    assert run.status is RunStatus.RUNNING
    assert run.last_seen_event_id > 0, "cursor must advance past node_a's completion event"
    assert run.context.data.get("a") == "done", "node_a's context_updates must be applied"

    completed_a = _latest_node(run_state, run_id, "node_a")
    assert completed_a is not None
    assert completed_a.status is NodeRunStatus.SUCCEEDED

    node_b = _latest_node(run_state, run_id, "node_b")
    assert node_b is not None
    assert node_b.status is NodeRunStatus.DISPATCHED
    assert node_b.task_id
    assert _kanban_task_status(node_b.task_id) is not None, "node_b task must exist in the real kanban DB"


def test_reconcile_to_completion_reaches_succeeded(
    hermes_home: Path,  # fixture sets up isolated env
    kanban: HermesKanbanBoard,
    tool_client: RuntimeToolClient,
    event_reader: SqliteTaskEventReader,
) -> None:
    """Completing both nodes and reconciling twice drives the run to SUCCEEDED at EXIT."""
    serializer = PydotSerializer()
    store = GitPipelineStore.from_env(None)
    run_state = SqliteRunStateStore(db_path=Path(os.environ["ATTRACTOR_DB_PATH"]))
    clock = SystemClock()
    spec_id = "reconcile_e2e_full"
    _author_linear_pipeline(store, serializer, spec_id)

    run_id = str(
        launch_run(
            spec_id=spec_id,
            initial_context={},
            kanban=kanban,
            run_state=run_state,
            serializer=serializer,
            store=store,
            clock=clock,
        )["run_id"]
    )

    node_a = _latest_node(run_state, run_id, "node_a")
    assert node_a is not None
    _complete(tool_client, node_a.task_id, summary="A done", metadata={})
    run_reconcile(tool_client=tool_client, event_reader=event_reader)

    node_b = _latest_node(run_state, run_id, "node_b")
    assert node_b is not None
    _complete(tool_client, node_b.task_id, summary="B done", metadata={})
    run_reconcile(tool_client=tool_client, event_reader=event_reader)

    run = run_state.get_run(run_id)
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED


@pytest.mark.parametrize("entrypoint", ["hook", "cli", "post_tool_call"])
def test_reconcile_entrypoint_advances_run(
    hermes_home: Path,  # fixture sets up isolated env
    kanban: HermesKanbanBoard,
    tool_client: RuntimeToolClient,
    entrypoint: str,
) -> None:
    """The on_session_start hook, the attractor-reconcile CLI, and post_tool_call all advance a run.

    These exercise the real runtime entry points (which build their own clients from env
    via ``_runtime_tool_client`` / ``_runtime_event_reader``), not just ``run_reconcile``.
    """
    serializer = PydotSerializer()
    store = GitPipelineStore.from_env(None)
    run_state = SqliteRunStateStore(db_path=Path(os.environ["ATTRACTOR_DB_PATH"]))
    clock = SystemClock()
    spec_id = f"reconcile_entry_{entrypoint}"
    _author_linear_pipeline(store, serializer, spec_id)

    run_id = str(
        launch_run(
            spec_id=spec_id,
            initial_context={},
            kanban=kanban,
            run_state=run_state,
            serializer=serializer,
            store=store,
            clock=clock,
        )["run_id"]
    )
    node_a = _latest_node(run_state, run_id, "node_a")
    assert node_a is not None
    _complete(tool_client, node_a.task_id, summary="A done", metadata={})

    if entrypoint == "hook":
        reconcile.reconcile_hook(task_id="ignored", session_id="ignored")  # accepts/ignores runtime kwargs
    elif entrypoint == "cli":
        reconcile.reconcile_cli_handler(None)
    else:
        # Simulate Hermes firing post_tool_call right after the worker's kanban_complete.
        reconcile.post_tool_call_hook(
            tool_name="kanban_complete",
            args={"task_id": node_a.task_id},
            result="{}",
            task_id=node_a.task_id,
        )

    node_b = _latest_node(run_state, run_id, "node_b")
    assert node_b is not None
    assert node_b.status is NodeRunStatus.DISPATCHED
    assert node_b.task_id


def test_attractor_run_builds_runtime_kanban_when_unset(
    hermes_home: Path,  # fixture sets up isolated env
) -> None:
    """handle_attractor_run with no injected kanban builds one from the live registry.

    Covers the ``_runtime_kanban`` seam: with no override the handler launches the run
    against the real kanban backend and returns ok:true with a run_id.
    """
    serializer = PydotSerializer()
    store = GitPipelineStore.from_env(None)
    _author_linear_pipeline(store, serializer, "rt_kanban")

    payload = json.loads(handle_attractor_run({"spec_id": "rt_kanban"}))

    assert payload["ok"] is True, payload
    assert "run_id" in payload["result"]
