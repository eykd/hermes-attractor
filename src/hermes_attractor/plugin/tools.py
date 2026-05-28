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
