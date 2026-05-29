"""Hermes tool handlers.

Each handler honors the Hermes contract: it accepts the parsed tool input, always
returns a JSON string, and never raises. Real logic is delegated to the use-case layer;
this module is the composition root that wires in concrete adapters.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from hermes_attractor import __version__
from hermes_attractor.adapters.dot_serializer import PydotSerializer
from hermes_attractor.adapters.pipeline_store import GitPipelineStore
from hermes_attractor.adapters.renderer import TextRenderer
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

if TYPE_CHECKING:
    from collections.abc import Callable


def _safe(produce: Callable[[], dict[str, object]]) -> str:
    """Run a handler body, converting any failure into an error JSON payload."""
    try:
        payload = produce()
    except Exception as exc:  # Hermes contract: handlers must never raise.
        return json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)})
    return json.dumps({"ok": True, "result": payload})


def _make_store(args: dict[str, object]) -> GitPipelineStore:
    """Construct a GitPipelineStore from the repo_path arg (or default cwd).

    Args:
        args: The tool input dict; may contain ``repo_path`` key.

    Returns:
        A GitPipelineStore rooted at the specified or default path.
    """
    repo_path = args.get("repo_path")
    root = Path(str(repo_path)) if repo_path else Path.cwd()
    return GitPipelineStore(repo_root=root)


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
        store = _make_store(args)
        serializer = PydotSerializer()
        updated = add_node(
            spec_id=spec_id,
            node_id=node_id,
            shape=shape,
            prompt=prompt,
            profile=profile,
            retry_limit=retry_limit,
            node_class=node_class,
            store=store,
            serializer=serializer,
        )
        return {"spec_id": spec_id, "node_id": node_id, "shape": updated.spec_id}

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
            StyleRule(selector=str(r["selector"]), profile=str(r["profile"]))  # type: ignore[index]
            for r in raw_rules
        ]
        store = _make_store(args)
        serializer = PydotSerializer()
        _ = set_stylesheet(spec_id=spec_id, rules=rules, store=store, serializer=serializer)
        return {"spec_id": spec_id, "rules_count": len(rules)}  # pragma: no cover

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
