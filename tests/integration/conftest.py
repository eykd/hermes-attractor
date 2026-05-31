"""Hermetic, reusable fixtures for the live hermes-agent integration suite.

Every fixture is isolated to a fresh ``tmp_path`` ``HERMES_HOME`` + kanban DB, so the
reconcile integration test is deterministic, order-independent, and re-runnable with no
external state, no ``hermes setup``, and no model key.

All ``hermes_cli`` / ``tools`` imports are performed lazily (via ``importlib``) inside
the fixtures so this conftest imports cleanly under the default (hermes-free) ``uv run
pytest`` — the fixtures are only ever instantiated by tests guarded with
``pytest.importorskip``.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import pytest

from hermes_attractor.adapters.event_log import HermesEventLog
from hermes_attractor.adapters.kanban_board import HermesKanbanBoard
from hermes_attractor.adapters.runtime_tool_client import RuntimeToolClient
from hermes_attractor.adapters.task_event_reader import SqliteTaskEventReader

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide an isolated HERMES_HOME + fresh kanban DB and register the kanban tools.

    Points ``HERMES_HOME`` / ``HERMES_KANBAN_DB`` and the attractor env vars at ``tmp_path``,
    ensures no dispatcher-worker scoping is active (``HERMES_KANBAN_TASK`` unset), eagerly
    creates the kanban schema, and imports ``tools.kanban_tools`` so ``kanban_*`` tools are
    registered in the runtime registry.

    Args:
        tmp_path: pytest's per-test temp directory.
        monkeypatch: pytest monkeypatch fixture for env isolation.

    Returns:
        The temp directory root used for all isolated state.
    """
    home = tmp_path / "home"
    home.mkdir()
    # Define the profiles the integration pipelines assign, so run-launch profile-existence
    # validation passes (hermes_cli.profiles.profile_exists checks HERMES_HOME/profiles/<name>).
    (home / "profiles" / "coder").mkdir(parents=True)
    kanban_db_path = tmp_path / "kanban.db"
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_DB", str(kanban_db_path))
    monkeypatch.setenv("ATTRACTOR_DB_PATH", str(tmp_path / "attractor_runs.db"))
    monkeypatch.setenv("ATTRACTOR_REPO_BASE", str(tmp_path))
    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_RUN_ID", raising=False)

    kanban_db = importlib.import_module("hermes_cli.kanban_db")
    kanban_db.connect(db_path=kanban_db_path).close()  # auto-creates the schema
    importlib.import_module("tools.kanban_tools")  # registers kanban_* tools in the registry
    return tmp_path


@pytest.fixture
def tool_client(hermes_home: Path) -> RuntimeToolClient:  # fixture dep for isolation
    """Return a RuntimeToolClient over the real runtime registry dispatch.

    Args:
        hermes_home: Ensures the isolated home + kanban tools are set up first.

    Returns:
        A RuntimeToolClient bound to ``tools.registry.registry.dispatch``.
    """
    registry = importlib.import_module("tools.registry").registry
    return RuntimeToolClient(dispatch=registry.dispatch)


@pytest.fixture
def event_reader(hermes_home: Path) -> SqliteTaskEventReader:  # fixture dep for isolation
    """Return a SqliteTaskEventReader over the real kanban DB connection.

    Args:
        hermes_home: Ensures the isolated home + kanban schema are set up first.

    Returns:
        A SqliteTaskEventReader bound to ``hermes_cli.kanban_db.connect``.
    """
    kanban_db = importlib.import_module("hermes_cli.kanban_db")
    return SqliteTaskEventReader(connect=kanban_db.connect)


@pytest.fixture
def kanban(tool_client: RuntimeToolClient) -> HermesKanbanBoard:
    """Return a HermesKanbanBoard over the real runtime tool client.

    Args:
        tool_client: The real RuntimeToolClient fixture.

    Returns:
        A HermesKanbanBoard bound to the live kanban tools.
    """
    return HermesKanbanBoard(tool_client=tool_client)


@pytest.fixture
def event_log(event_reader: SqliteTaskEventReader) -> HermesEventLog:
    """Return a HermesEventLog over the real task-event reader.

    Args:
        event_reader: The real SqliteTaskEventReader fixture.

    Returns:
        A HermesEventLog bound to the live kanban ``task_events`` log.
    """
    return HermesEventLog(reader=event_reader)
