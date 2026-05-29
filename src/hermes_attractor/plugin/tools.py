"""Hermes tool handlers.

Each handler honors the Hermes contract: it accepts the parsed tool input, always
returns a JSON string, and never raises. Real logic is delegated to the use-case layer;
this module is the composition root that wires in concrete adapters.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from hermes_attractor import __version__
from hermes_attractor.adapters.system_clock import SystemClock
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


def _not_implemented(tool_name: str) -> str:
    """Return a standard 'not implemented' JSON error payload for stub handlers."""
    msg = f"{tool_name!r} is not yet implemented (M1 authoring milestone pending)"
    return json.dumps({"ok": False, "error": "NotImplementedError", "message": msg})


# ---------------------------------------------------------------------------
# Authoring tool stubs (M1 — to be implemented in the authoring milestone).
# These stubs make acceptance tests importable so the ATDD outer loop can
# declare failing tests. Each stub returns ok:false with a clear message.
# ---------------------------------------------------------------------------


def handle_attractor_create_graph(args: dict[str, object]) -> str:
    """Handle the ``attractor_create_graph`` tool (STUB — M1 not yet implemented).

    Expected inputs: spec_id (str), optional repo_path (str).
    """
    return _not_implemented("attractor_create_graph")


def handle_attractor_add_node(args: dict[str, object]) -> str:
    """Handle the ``attractor_add_node`` tool (STUB — M1 not yet implemented).

    Expected inputs: spec_id, node_id, shape, optional prompt/profile/retry_limit/goal_gate/class.
    """
    return _not_implemented("attractor_add_node")


def handle_attractor_remove_node(args: dict[str, object]) -> str:
    """Handle the ``attractor_remove_node`` tool (STUB — M1 not yet implemented).

    Expected inputs: spec_id, node_id.
    """
    return _not_implemented("attractor_remove_node")


def handle_attractor_add_edge(args: dict[str, object]) -> str:
    """Handle the ``attractor_add_edge`` tool (STUB — M1 not yet implemented).

    Expected inputs: spec_id, source_id, target_id, optional condition/label/weight.
    """
    return _not_implemented("attractor_add_edge")


def handle_attractor_remove_edge(args: dict[str, object]) -> str:
    """Handle the ``attractor_remove_edge`` tool (STUB — M1 not yet implemented).

    Expected inputs: spec_id, source_id, target_id, optional label.
    """
    return _not_implemented("attractor_remove_edge")


def handle_attractor_set_stylesheet(args: dict[str, object]) -> str:
    """Handle the ``attractor_set_stylesheet`` tool (STUB — M1 not yet implemented).

    Expected inputs: spec_id, rules (list of selector/profile mappings).
    """
    return _not_implemented("attractor_set_stylesheet")


def handle_attractor_validate(args: dict[str, object]) -> str:
    """Handle the ``attractor_validate`` tool (STUB — M1 not yet implemented).

    Expected inputs: spec_id.
    Result: {valid: bool, issues: [{element_id, reason}]}.
    """
    return _not_implemented("attractor_validate")


def handle_attractor_summary(args: dict[str, object]) -> str:
    """Handle the ``attractor_summary`` tool (STUB — M1 not yet implemented).

    Expected inputs: spec_id.
    Result: {summary: str, dot: str}.
    """
    return _not_implemented("attractor_summary")
