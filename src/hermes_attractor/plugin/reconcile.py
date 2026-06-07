"""Reconcile wiring for the attractor plugin (zym.29 Part B).

Composes the reconcile use case over env-based stores and the runtime kanban tool
surface, and exposes the thin Hermes-coupled entry points registered by
``plugin/__init__.py``:

- ``reconcile_hook(**kwargs)`` — the ``on_session_start`` lifecycle hook.
- ``reconcile_cli_handler(args)`` + ``reconcile_setup(subparser)`` — the
  ``attractor-reconcile`` CLI command.

The pure, fully-tested core is :func:`run_reconcile`, which accepts an injected
``tool_client`` (a :class:`HermesToolClient`) and ``event_reader`` (a
:class:`TaskEventReader`). The Hermes runtime is only touched inside the
``# pragma: no cover`` builders (:func:`_runtime_tool_client` / :func:`_runtime_event_reader`),
which lazily import ``tools.registry`` and ``hermes_cli.kanban_db`` — neither is in the
locked deps, so those imports must stay inside functions. See
``specs/001-attractor-kanban/research-hermes-kanban.md`` §Phase 1.

See: specs/001-attractor-kanban/contracts/tools.md §CLI command
"""

from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

from hermes_attractor.adapters.dot_serializer import PydotSerializer
from hermes_attractor.adapters.event_log import HermesEventLog
from hermes_attractor.adapters.kanban_board import HermesKanbanBoard
from hermes_attractor.adapters.pipeline_store import GitPipelineStore
from hermes_attractor.adapters.run_state_store import SqliteRunStateStore
from hermes_attractor.adapters.runtime_tool_client import RuntimeToolClient
from hermes_attractor.adapters.system_clock import SystemClock
from hermes_attractor.adapters.task_event_reader import SqliteTaskEventReader
from hermes_attractor.use_cases.reconcile import reconcile
from hermes_attractor.use_cases.run_execution import advance_on_completion

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable

    from hermes_attractor.ports.clock import Clock
    from hermes_attractor.ports.dot import DotSerializer
    from hermes_attractor.ports.hermes_tool_client import HermesToolClient
    from hermes_attractor.ports.pipeline_store import PipelineStore
    from hermes_attractor.ports.run_state import RunStateStore
    from hermes_attractor.ports.task_event_reader import TaskEventReader

__all__ = [
    "post_tool_call_hook",
    "reconcile_cli_handler",
    "reconcile_hook",
    "reconcile_setup",
    "run_reconcile",
]

_log = logging.getLogger(__name__)

#: The kanban tool whose completion drives inline run advancement (research §Run advancement,
#: primary path). Other terminal kinds (blocked / crashed / timed_out / gave_up) are never
#: observed by ``post_tool_call`` (a living worker only emits ``kanban_complete``) and are
#: handled by the reconcile recovery path instead.
_ADVANCE_ON_TOOL = "kanban_complete"


def _make_run_state_store() -> SqliteRunStateStore:
    """Construct a SqliteRunStateStore from ``ATTRACTOR_DB_PATH`` or Hermes home.

    Mirrors ``plugin.tools._make_run_state_store`` so the hook/CLI path uses the same
    run-state database the execution tools write to.

    Returns:
        A SqliteRunStateStore backed by the configured database path.
    """
    env_db = os.environ.get("ATTRACTOR_DB_PATH")
    hermes_home = os.environ.get("HERMES_HOME")
    if env_db:
        db_path = Path(env_db)
    elif hermes_home:
        db_path = Path(hermes_home) / "attractor_runs.db"
    else:
        db_path = Path.cwd() / "attractor_runs.db"
    return SqliteRunStateStore(db_path=db_path)


def run_reconcile(  # noqa: PLR0913
    *,
    tool_client: HermesToolClient,
    event_reader: TaskEventReader,
    run_state: RunStateStore | None = None,
    store: PipelineStore | None = None,
    serializer: DotSerializer | None = None,
    clock: Clock | None = None,
    advance_fn: Callable[..., None] | None = None,
) -> None:
    """Replay unprocessed kanban completion events and advance all active runs.

    Builds the env-based stores (run-state DB, git pipeline store) and the kanban
    adapters over the injected ``tool_client`` / ``event_reader``, then runs the
    :func:`~hermes_attractor.use_cases.reconcile.reconcile` use case with
    ``advance_on_completion`` as the advancement function.

    Args:
        tool_client: HermesToolClient for creating follow-up cards (KanbanBoard side).
        event_reader: TaskEventReader for tailing the terminal ``task_events`` log.
        run_state: Optional RunStateStore override (defaults to ``ATTRACTOR_DB_PATH``).
        store: Optional PipelineStore override (defaults to ``GitPipelineStore.from_env``).
        serializer: Optional DotSerializer override (defaults to ``PydotSerializer``).
        clock: Optional Clock override (defaults to ``SystemClock``).
        advance_fn: Optional advancement function override (defaults to
            ``advance_on_completion``).
    """
    _run_state = run_state if run_state is not None else _make_run_state_store()
    _store = store if store is not None else GitPipelineStore.from_env(None)
    _serializer = serializer if serializer is not None else PydotSerializer()
    _clock = clock if clock is not None else SystemClock()
    _advance = advance_fn if advance_fn is not None else advance_on_completion

    reconcile(
        run_state=_run_state,
        event_log=HermesEventLog(reader=event_reader),
        serializer=_serializer,
        store=_store,
        kanban=HermesKanbanBoard(tool_client=tool_client),
        clock=_clock,
        advance_fn=_advance,
    )


def _runtime_tool_client() -> HermesToolClient:
    """Build a RuntimeToolClient over the live ``tools.registry`` dispatch.

    ``tools.registry`` is provided by the host hermes runtime (and by the ``test``
    dependency group for the integration suite); it is imported by name via ``importlib``
    so it stays out of the plugin's runtime deps and out of static import resolution.
    """
    registry = importlib.import_module("tools.registry").registry
    dispatch = cast("Callable[..., str]", registry.dispatch)
    return RuntimeToolClient(dispatch=dispatch)


def _runtime_event_reader() -> TaskEventReader:
    """Build a SqliteTaskEventReader over the live kanban DB connection.

    ``hermes_cli.kanban_db`` is provided by the host hermes runtime (and by the ``test``
    dependency group for the integration suite); it is imported by name via ``importlib``
    so it stays out of the plugin's runtime deps and out of static import resolution.
    """
    kanban_db = importlib.import_module("hermes_cli.kanban_db")
    connect = cast("Callable[..., sqlite3.Connection]", kanban_db.connect)
    return SqliteTaskEventReader(connect=connect)


def reconcile_hook(**_kwargs: object) -> None:
    """``on_session_start`` hook: reconcile active runs against the kanban event log.

    Builds the runtime clients from the live registry / kanban DB and delegates to
    :func:`run_reconcile`. Never raises — a reconcile failure must not break session
    startup (``PluginManager.invoke_hook`` also guards, but we are defensive here).

    Args:
        **_kwargs: Runtime context kwargs from the Hermes host (ignored).
    """
    try:
        run_reconcile(tool_client=_runtime_tool_client(), event_reader=_runtime_event_reader())
    except Exception:  # noqa: BLE001  # hook must never break session startup
        _log.exception("attractor reconcile hook failed")


def post_tool_call_hook(*, tool_name: str = "", **_kwargs: object) -> None:
    """``post_tool_call`` hook: advance runs inline right after a worker completes a card.

    This is the primary (low-latency) advancement path: when a dispatcher-spawned worker
    calls ``kanban_complete``, Hermes fires ``post_tool_call`` synchronously *after* the
    tool committed its ``completed`` event (verified against ``model_tools.py``), so a
    reconcile pass here sees the new event and creates the follow-up card before the worker
    exits. It is gated to ``kanban_complete`` so it is a no-op after every other tool call.

    Advancement reuses the idempotent :func:`run_reconcile`, so it is safe alongside the
    ``on_session_start`` / ``attractor-reconcile`` recovery path (cursor-based, no double
    advance). Never raises — a failure must not break the worker's tool cycle.

    Args:
        tool_name: The name of the tool that was just dispatched.
        **_kwargs: Other runtime kwargs (``args``, ``result``, ``task_id``, …); ignored.
    """
    if tool_name != _ADVANCE_ON_TOOL:
        return
    try:
        run_reconcile(tool_client=_runtime_tool_client(), event_reader=_runtime_event_reader())
    except Exception:  # noqa: BLE001  # hook must never break the worker's tool cycle
        _log.exception("attractor post_tool_call advance failed")


def reconcile_setup(_subparser: object) -> None:
    """Configure the ``attractor-reconcile`` CLI subparser (no arguments needed).

    Args:
        _subparser: The argparse subparser supplied by the Hermes host (unused).
    """


def reconcile_cli_handler(_args: object) -> None:
    """``attractor-reconcile`` CLI handler: run a one-shot reconcile pass.

    Args:
        _args: The parsed argparse namespace from the Hermes host (unused).
    """
    run_reconcile(tool_client=_runtime_tool_client(), event_reader=_runtime_event_reader())
