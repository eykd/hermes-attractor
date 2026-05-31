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

__all__ = ["reconcile_cli_handler", "reconcile_hook", "reconcile_setup", "run_reconcile"]

_log = logging.getLogger(__name__)


def _make_run_state_store() -> SqliteRunStateStore:
    """Construct a SqliteRunStateStore from ``ATTRACTOR_DB_PATH`` (or default cwd).

    Mirrors ``plugin.tools._make_run_state_store`` so the hook/CLI path uses the same
    run-state database the execution tools write to.

    Returns:
        A SqliteRunStateStore backed by the configured database path.
    """
    env_db = os.environ.get("ATTRACTOR_DB_PATH")
    db_path = Path(env_db) if env_db else Path.cwd() / "attractor_runs.db"
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


def _runtime_tool_client() -> HermesToolClient:  # pragma: no cover - requires the live hermes runtime
    """Build a RuntimeToolClient over the live ``tools.registry`` dispatch.

    ``tools.registry`` is not in the locked deps; it is imported by name via
    ``importlib`` (the runtime worker process provides it) so static analysis does not
    need to resolve it.
    """
    registry = importlib.import_module("tools.registry").registry
    dispatch = cast("Callable[..., str]", registry.dispatch)
    return RuntimeToolClient(dispatch=dispatch)


def _runtime_event_reader() -> TaskEventReader:  # pragma: no cover - requires the live hermes runtime
    """Build a SqliteTaskEventReader over the live kanban DB connection.

    ``hermes_cli.kanban_db`` is not in the locked deps; it is imported by name via
    ``importlib`` so static analysis does not need to resolve it.
    """
    kanban_db = importlib.import_module("hermes_cli.kanban_db")
    connect = cast("Callable[..., sqlite3.Connection]", kanban_db.connect)
    return SqliteTaskEventReader(connect=connect)


def reconcile_hook(**_kwargs: object) -> None:  # pragma: no cover - requires the live hermes runtime
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


def reconcile_setup(_subparser: object) -> None:  # pragma: no cover - requires the live hermes runtime
    """Configure the ``attractor-reconcile`` CLI subparser (no arguments needed).

    Args:
        _subparser: The argparse subparser supplied by the Hermes host (unused).
    """


def reconcile_cli_handler(_args: object) -> None:  # pragma: no cover - requires the live hermes runtime
    """``attractor-reconcile`` CLI handler: run a one-shot reconcile pass.

    Args:
        _args: The parsed argparse namespace from the Hermes host (unused).
    """
    run_reconcile(tool_client=_runtime_tool_client(), event_reader=_runtime_event_reader())
