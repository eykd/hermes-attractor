"""Hermes entry shim for the attractor plugin.

This is the only Hermes-coupled layer. ``register`` wires all tool schemas to
their handlers via the host ``PluginContext``; all real logic lives in the
hexagonal core (domain / use_cases / adapters).

Tool handlers are wrapped in a thin runtime adapter that drops unknown keyword
arguments forwarded by the Hermes runtime (e.g. ``task_id``, ``session_id``),
while preserving the keyword-override signatures used in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hermes_attractor.plugin import schemas, tools

if TYPE_CHECKING:
    from collections.abc import Callable

    from hermes_attractor.ports.hermes import PluginContext, ToolHandler

__all__ = ["register"]

_TOOLSET = "attractor"


def _runtime(handler: Callable[[dict[str, object]], str]) -> ToolHandler:
    """Wrap a handler to silently drop unknown runtime kwargs from the Hermes host.

    The Hermes runtime calls handlers as ``handler(args, **kwargs)`` with
    extra context values (``task_id``, ``session_id``, …).  Our handlers take
    only positional ``args``; this shim absorbs the extras without touching the
    handler's own keyword-override params (used in tests).

    Args:
        handler: A tool handler callable.

    Returns:
        A :class:`~hermes_attractor.ports.hermes.ToolHandler` that accepts
        ``(args, **_kw)`` and forwards only ``args`` to the underlying handler.
    """

    class _Adapter:
        """Runtime adapter that absorbs extra kwargs from the Hermes host."""

        def __call__(self, args: dict[str, object], **_kw: object) -> str:
            """Forward args to the handler, discarding any runtime kwargs."""
            return handler(args)

    return _Adapter()


def register(ctx: PluginContext) -> None:
    """Register all attractor plugin tools with the Hermes host.

    Registers 13 tools: health, echo, and the 11 attractor authoring/execution
    tools.  Hook and CLI-command registration is deferred to Part B.
    """
    # -- Utility tools -------------------------------------------------------
    ctx.register_tool(
        "health",
        _TOOLSET,
        schemas.HEALTH_SCHEMA,
        _runtime(tools.handle_health),
    )
    ctx.register_tool(
        "echo",
        _TOOLSET,
        schemas.ECHO_SCHEMA,
        _runtime(tools.handle_echo),
    )

    # -- M1 Authoring tools --------------------------------------------------
    ctx.register_tool(
        "attractor_create_graph",
        _TOOLSET,
        schemas.ATTRACTOR_CREATE_GRAPH_SCHEMA,
        _runtime(tools.handle_attractor_create_graph),
    )
    ctx.register_tool(
        "attractor_add_node",
        _TOOLSET,
        schemas.ATTRACTOR_ADD_NODE_SCHEMA,
        _runtime(tools.handle_attractor_add_node),
    )
    ctx.register_tool(
        "attractor_remove_node",
        _TOOLSET,
        schemas.ATTRACTOR_REMOVE_NODE_SCHEMA,
        _runtime(tools.handle_attractor_remove_node),
    )
    ctx.register_tool(
        "attractor_add_edge",
        _TOOLSET,
        schemas.ATTRACTOR_ADD_EDGE_SCHEMA,
        _runtime(tools.handle_attractor_add_edge),
    )
    ctx.register_tool(
        "attractor_remove_edge",
        _TOOLSET,
        schemas.ATTRACTOR_REMOVE_EDGE_SCHEMA,
        _runtime(tools.handle_attractor_remove_edge),
    )
    ctx.register_tool(
        "attractor_set_stylesheet",
        _TOOLSET,
        schemas.ATTRACTOR_SET_STYLESHEET_SCHEMA,
        _runtime(tools.handle_attractor_set_stylesheet),
    )
    ctx.register_tool(
        "attractor_validate",
        _TOOLSET,
        schemas.ATTRACTOR_VALIDATE_SCHEMA,
        _runtime(tools.handle_attractor_validate),
    )
    ctx.register_tool(
        "attractor_summary",
        _TOOLSET,
        schemas.ATTRACTOR_SUMMARY_SCHEMA,
        _runtime(tools.handle_attractor_summary),
    )

    # -- M2 Execution tools --------------------------------------------------
    ctx.register_tool(
        "attractor_run",
        _TOOLSET,
        schemas.ATTRACTOR_RUN_SCHEMA,
        _runtime(tools.handle_attractor_run),
    )
    ctx.register_tool(
        "attractor_status",
        _TOOLSET,
        schemas.ATTRACTOR_STATUS_SCHEMA,
        _runtime(tools.handle_attractor_status),
    )
    ctx.register_tool(
        "attractor_result",
        _TOOLSET,
        schemas.ATTRACTOR_RESULT_SCHEMA,
        _runtime(tools.handle_attractor_result),
    )
