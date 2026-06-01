"""Hermes tool handlers.

Each handler honors the Hermes contract: it accepts the parsed tool input, always
returns a JSON string, and never raises. Real logic is delegated to the use-case layer;
this module is the composition root that wires in concrete adapters.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

from hermes_attractor import __version__
from hermes_attractor.adapters.dot_serializer import PydotSerializer
from hermes_attractor.adapters.kanban_board import HermesKanbanBoard
from hermes_attractor.adapters.pipeline_store import GitPipelineStore
from hermes_attractor.adapters.profile_provisioner import HermesProfileProvisioner
from hermes_attractor.adapters.profile_registry import HermesProfileRegistry
from hermes_attractor.adapters.renderer import TextRenderer
from hermes_attractor.adapters.run_state_store import SqliteRunStateStore
from hermes_attractor.adapters.runtime_tool_client import RuntimeToolClient
from hermes_attractor.adapters.system_clock import SystemClock
from hermes_attractor.domain.pipeline import NodeShape, StyleRule
from hermes_attractor.use_cases.authoring import (
    add_edge,
    add_node,
    create_graph,
    get_summary,
    remove_edge,
    remove_node,
    set_stylesheet,
    validate_pipeline,
)
from hermes_attractor.use_cases.echo import echo
from hermes_attractor.use_cases.health import check_health
from hermes_attractor.use_cases.provisioning import provision_profiles
from hermes_attractor.use_cases.run_execution import launch_run, query_run_result, query_run_status

if TYPE_CHECKING:
    from collections.abc import Callable

    from hermes_attractor.ports.clock import Clock
    from hermes_attractor.ports.dot import DotSerializer
    from hermes_attractor.ports.kanban import KanbanBoard
    from hermes_attractor.ports.pipeline_store import PipelineStore
    from hermes_attractor.ports.profile_provisioner import ProfileProvisioner
    from hermes_attractor.ports.profile_registry import ProfileRegistry
    from hermes_attractor.ports.run_state import RunStateStore


def _safe(produce: Callable[[], dict[str, object]]) -> str:
    """Run a handler body, converting any failure into an error JSON payload."""
    try:
        payload = produce()
    except Exception as exc:  # Hermes contract: handlers must never raise.
        return json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)})
    return json.dumps({"ok": True, "result": payload})


def _make_run_state_store() -> SqliteRunStateStore:
    """Construct a SqliteRunStateStore from the ATTRACTOR_DB_PATH env var (or default cwd).

    Reads the ``ATTRACTOR_DB_PATH`` environment variable if set; otherwise defaults to
    ``Path.cwd() / "attractor_runs.db"``.  Mirrors the ``_make_store()`` /
    ``ATTRACTOR_REPO_BASE`` pattern.

    Returns:
        A SqliteRunStateStore backed by the configured database path.
    """
    env_db = os.environ.get("ATTRACTOR_DB_PATH")
    db_path = Path(env_db) if env_db else Path.cwd() / "attractor_runs.db"
    return SqliteRunStateStore(db_path=db_path)


def _runtime_kanban() -> KanbanBoard:
    """Build a KanbanBoard over the live Hermes tool registry dispatch.

    Used by ``handle_attractor_run`` when no kanban override is injected: the runtime
    tool registry (provided by the host, and by the ``test`` dependency group for the
    integration suite) is imported by name via ``importlib`` and wrapped in a
    :class:`RuntimeToolClient`. See research §Phase 1 (A).

    Returns:
        A HermesKanbanBoard bound to the live runtime dispatch seam.
    """
    registry = importlib.import_module("tools.registry").registry
    dispatch = cast("Callable[..., str]", registry.dispatch)
    return HermesKanbanBoard(tool_client=RuntimeToolClient(dispatch=dispatch))


def _make_store(args: dict[str, object]) -> GitPipelineStore:
    """Construct a GitPipelineStore from the repo_path arg (or default cwd).

    Delegates path confinement validation to
    :meth:`~hermes_attractor.adapters.pipeline_store.GitPipelineStore.from_env`.

    Args:
        args: The tool input dict; may contain ``repo_path`` key.

    Returns:
        A GitPipelineStore rooted at the confined path.

    Raises:
        RepoPathConfinementError: If ``repo_path`` escapes the allowed base.
    """
    repo_path = args.get("repo_path")
    return GitPipelineStore.from_env(str(repo_path) if repo_path else None)


# ---------------------------------------------------------------------------
# Existing tools
# ---------------------------------------------------------------------------


def handle_health(args: dict[str, object]) -> str:
    """Handle the ``health`` tool: report status and version."""

    def _produce() -> dict[str, object]:
        report = check_health(clock=SystemClock(), version=__version__)
        return report.to_dict()

    return _safe(_produce)


def handle_echo(args: dict[str, object]) -> str:
    """Handle the ``echo`` tool: echo the ``message`` argument back."""

    def _produce() -> dict[str, object]:
        raw = args.get("message")
        message = echo("" if raw is None else str(raw))
        return {"message": message.value}

    return _safe(_produce)


# ---------------------------------------------------------------------------
# Authoring tool handlers (M1)
# ---------------------------------------------------------------------------


def handle_attractor_create_graph(args: dict[str, object]) -> str:
    """Handle the ``attractor_create_graph`` tool.

    Expected inputs: spec_id (str), optional repo_path (str).
    """

    def _produce() -> dict[str, object]:
        spec_id = str(args["spec_id"])
        store = _make_store(args)
        serializer = PydotSerializer()
        create_graph(spec_id=spec_id, store=store, serializer=serializer)
        return {"spec_id": spec_id}

    return _safe(_produce)


def handle_attractor_add_node(args: dict[str, object]) -> str:
    """Handle the ``attractor_add_node`` tool.

    Expected inputs: spec_id, node_id, shape, optional prompt/profile/retry_limit/class.
    """

    def _produce() -> dict[str, object]:
        spec_id = str(args["spec_id"])
        node_id = str(args["node_id"])
        shape_str = str(args["shape"])
        shape = NodeShape[shape_str]
        prompt = str(args["prompt"]) if args.get("prompt") else None
        profile = str(args["profile"]) if args.get("profile") else None
        retry_limit = int(str(args.get("retry_limit") or 0))
        node_class = str(args["class"]) if args.get("class") else None
        retry_target = str(args["retry_target"]) if args.get("retry_target") else None
        max_attempts_raw = args.get("max_attempts")
        max_attempts = int(str(max_attempts_raw)) if max_attempts_raw is not None else None
        store = _make_store(args)
        serializer = PydotSerializer()
        _ = add_node(
            spec_id=spec_id,
            node_id=node_id,
            shape=shape,
            prompt=prompt,
            profile=profile,
            retry_limit=retry_limit,
            node_class=node_class,
            retry_target=retry_target,
            max_attempts=max_attempts,
            store=store,
            serializer=serializer,
        )
        return {"spec_id": spec_id, "node_id": node_id, "shape": shape_str}

    return _safe(_produce)


def handle_attractor_remove_node(args: dict[str, object]) -> str:
    """Handle the ``attractor_remove_node`` tool.

    Expected inputs: spec_id, node_id.
    """

    def _produce() -> dict[str, object]:
        spec_id = str(args["spec_id"])
        node_id = str(args["node_id"])
        store = _make_store(args)
        serializer = PydotSerializer()
        _ = remove_node(spec_id=spec_id, node_id=node_id, store=store, serializer=serializer)
        return {"spec_id": spec_id, "removed": node_id}

    return _safe(_produce)


def handle_attractor_add_edge(args: dict[str, object]) -> str:
    """Handle the ``attractor_add_edge`` tool.

    Expected inputs: spec_id, source_id, target_id, optional condition/label/weight.
    """

    def _produce() -> dict[str, object]:
        spec_id = str(args["spec_id"])
        source_id = str(args["source_id"])
        target_id = str(args["target_id"])
        condition = str(args["condition"]) if args.get("condition") else None
        label = str(args["label"]) if args.get("label") else None
        weight = int(str(args.get("weight") or 0))
        store = _make_store(args)
        serializer = PydotSerializer()
        _ = add_edge(
            spec_id=spec_id,
            source_id=source_id,
            target_id=target_id,
            condition=condition,
            label=label,
            weight=weight,
            store=store,
            serializer=serializer,
        )
        return {"spec_id": spec_id, "source_id": source_id, "target_id": target_id}

    return _safe(_produce)


def handle_attractor_remove_edge(args: dict[str, object]) -> str:
    """Handle the ``attractor_remove_edge`` tool.

    Expected inputs: spec_id, source_id, target_id, optional label.
    """

    def _produce() -> dict[str, object]:
        spec_id = str(args["spec_id"])
        source_id = str(args["source_id"])
        target_id = str(args["target_id"])
        label = str(args["label"]) if args.get("label") else None
        store = _make_store(args)
        serializer = PydotSerializer()
        _ = remove_edge(
            spec_id=spec_id,
            source_id=source_id,
            target_id=target_id,
            label=label,
            store=store,
            serializer=serializer,
        )
        return {"spec_id": spec_id, "removed": f"{source_id}->{target_id}"}

    return _safe(_produce)


def handle_attractor_set_stylesheet(args: dict[str, object]) -> str:
    """Handle the ``attractor_set_stylesheet`` tool.

    Expected inputs: spec_id, rules (list of {selector, profile} dicts).
    """

    def _produce() -> dict[str, object]:
        spec_id = str(args["spec_id"])
        raw_rules_obj = args.get("rules")
        raw_rules: list[object] = (
            list(raw_rules_obj)  # pyright: ignore[reportUnknownArgumentType]
            if isinstance(raw_rules_obj, list)
            else []
        )
        rules = [
            StyleRule(selector=str(r["selector"]), profile=str(r["profile"]))  # pyright: ignore[reportIndexIssue, reportUnknownArgumentType]
            for r in raw_rules
        ]
        store = _make_store(args)
        serializer = PydotSerializer()
        _ = set_stylesheet(spec_id=spec_id, rules=rules, store=store, serializer=serializer)
        return {"spec_id": spec_id, "rules_count": len(rules)}

    return _safe(_produce)


def handle_attractor_validate(args: dict[str, object]) -> str:
    """Handle the ``attractor_validate`` tool.

    Expected inputs: spec_id.
    Result: {valid: bool, issues: [{element_id, reason}]}.
    """

    def _produce() -> dict[str, object]:
        spec_id = str(args["spec_id"])
        store = _make_store(args)
        serializer = PydotSerializer()
        return validate_pipeline(spec_id=spec_id, store=store, serializer=serializer)

    return _safe(_produce)


def handle_attractor_summary(args: dict[str, object]) -> str:
    """Handle the ``attractor_summary`` tool.

    Expected inputs: spec_id.
    Result: {summary: str, dot: str}.
    """

    def _produce() -> dict[str, object]:
        spec_id = str(args["spec_id"])
        store = _make_store(args)
        serializer = PydotSerializer()
        renderer = TextRenderer()
        return get_summary(spec_id=spec_id, store=store, serializer=serializer, renderer=renderer)

    return _safe(_produce)


# ---------------------------------------------------------------------------
# Execution tool handlers (M2)
# ---------------------------------------------------------------------------


def handle_attractor_run(  # noqa: PLR0913
    args: dict[str, object],
    *,
    kanban: KanbanBoard | None = None,
    run_state: RunStateStore | None = None,
    serializer: DotSerializer | None = None,
    store: PipelineStore | None = None,
    clock: Clock | None = None,
    profile_registry: ProfileRegistry | None = None,
) -> str:
    """Handle the ``attractor_run`` tool: launch a new pipeline run.

    Expected inputs: spec_id (str), optional repo_path (str), optional context (dict).

    Args:
        args: Tool input dict containing ``spec_id`` and optionally ``context``.
        kanban: Optional KanbanBoard override (for testing).
        run_state: Optional RunStateStore override (for testing).
        serializer: Optional DotSerializer override (for testing).
        store: Optional PipelineStore override (for testing).
        clock: Optional Clock override (for testing).
        profile_registry: Optional ProfileRegistry override (for testing); defaults to the
            host-backed :class:`HermesProfileRegistry` so unknown profiles are rejected.
    """

    def _produce() -> dict[str, object]:
        spec_id = str(args["spec_id"])
        raw_context = args.get("context")
        if isinstance(raw_context, dict):
            raw_ctx = cast("dict[str, object]", raw_context)
            initial_context: dict[str, object] = dict(raw_ctx)
        else:
            initial_context = {}

        _store = store if store is not None else _make_store(args)
        _serializer = serializer if serializer is not None else PydotSerializer()
        _clock = clock if clock is not None else SystemClock()

        _run_state = run_state if run_state is not None else _make_run_state_store()

        _kanban = kanban if kanban is not None else _runtime_kanban()

        _profile_registry = profile_registry if profile_registry is not None else HermesProfileRegistry()

        return launch_run(
            spec_id=spec_id,
            initial_context=initial_context,
            kanban=_kanban,
            run_state=_run_state,
            serializer=_serializer,
            store=_store,
            clock=_clock,
            profile_registry=_profile_registry,
        )

    return _safe(_produce)


def handle_attractor_status(
    args: dict[str, object],
    *,
    run_state: RunStateStore | None = None,
) -> str:
    """Handle the ``attractor_status`` tool: query run status.

    Expected inputs: run_id (str).

    Args:
        args: Tool input dict containing ``run_id``.
        run_state: Optional RunStateStore override (for testing).
    """

    def _produce() -> dict[str, object]:
        run_id = str(args["run_id"])
        _run_state = run_state if run_state is not None else _make_run_state_store()
        return query_run_status(run_id=run_id, run_state=_run_state)

    return _safe(_produce)


def handle_attractor_result(
    args: dict[str, object],
    *,
    run_state: RunStateStore | None = None,
) -> str:
    """Handle the ``attractor_result`` tool: retrieve run outcome.

    Expected inputs: run_id (str).

    Args:
        args: Tool input dict containing ``run_id``.
        run_state: Optional RunStateStore override (for testing).
    """

    def _produce() -> dict[str, object]:
        run_id = str(args["run_id"])
        _run_state = run_state if run_state is not None else _make_run_state_store()
        return query_run_result(run_id=run_id, run_state=_run_state)

    return _safe(_produce)


def handle_attractor_provision_profiles(
    args: dict[str, object],
    *,
    store: PipelineStore | None = None,
    serializer: DotSerializer | None = None,
    registry: ProfileRegistry | None = None,
    provisioner: ProfileProvisioner | None = None,
) -> str:
    """Handle the ``attractor_provision_profiles`` tool: create a pipeline's missing profiles.

    Expected inputs: spec_id (str), optional repo_path (str), optional base_profile (str),
    optional models ({tier: model} map). Result: {spec_id, created: [str], existing: [str]}.

    Args:
        args: Tool input dict containing ``spec_id`` and optionally ``repo_path`` /
            ``base_profile`` / ``models``.
        store: Optional PipelineStore override (for testing).
        serializer: Optional DotSerializer override (for testing).
        registry: Optional ProfileRegistry override (for testing).
        provisioner: Optional ProfileProvisioner override (for testing).
    """

    def _produce() -> dict[str, object]:
        spec_id = str(args["spec_id"])
        _store = store if store is not None else _make_store(args)
        _serializer = serializer if serializer is not None else PydotSerializer()
        pipeline = _serializer.parse(_store.load(spec_id))

        _registry = registry if registry is not None else HermesProfileRegistry()
        if provisioner is not None:
            _provisioner = provisioner
        else:
            base_raw = args.get("base_profile")
            _provisioner = HermesProfileProvisioner(clone_from=str(base_raw) if base_raw else None)

        raw_models = args.get("models")
        models = (
            {str(k): str(v) for k, v in cast("dict[str, object]", raw_models).items()}
            if isinstance(raw_models, dict)
            else None
        )

        report = provision_profiles(
            profiles=pipeline.resolved_worker_profiles().values(),
            registry=_registry,
            provisioner=_provisioner,
            models=models,
        )
        return {"spec_id": spec_id, **report}

    return _safe(_produce)
