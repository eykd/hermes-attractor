"""Hermes entry shim for the attractor plugin.

This is the only Hermes-coupled layer. ``register`` wires the tool schemas to their
handlers; all real logic lives in the hexagonal core (domain / use_cases / adapters).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hermes_attractor.plugin import schemas, tools

if TYPE_CHECKING:
    from hermes_attractor.ports.hermes import PluginContext

__all__ = ["register"]


def register(ctx: PluginContext) -> None:
    """Register the attractor plugin's tools with the Hermes host."""
    ctx.register_tool(name="health", schema=schemas.HEALTH_SCHEMA, handler=tools.handle_health)
    ctx.register_tool(name="echo", schema=schemas.ECHO_SCHEMA, handler=tools.handle_echo)
