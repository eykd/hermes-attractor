"""InMemoryToolNodeRegistry adapter: explicit allowlist for TOOL node dispatch.

Never performs dynamic import. Unknown tool names return a safe error result,
never raise an exception (plan.md §Security §Tool-node allowlisting).

See: specs/001-attractor-kanban/contracts/ports.md §ToolNodeRegistry
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from hermes_attractor.domain.pipeline import Context

_log = logging.getLogger(__name__)

#: Result status for an unknown tool name.
_STATUS_UNKNOWN_TOOL = "UNKNOWN_TOOL"
#: Result status for a successful tool invocation.
_STATUS_SUCCESS = "SUCCESS"
#: Result status for a tool that raised an exception.
_STATUS_ERROR = "ERROR"


class InMemoryToolNodeRegistry:
    """In-memory ToolNodeRegistry backed by an explicit name -> callable allowlist.

    Tools are registered at startup; no dynamic import is ever performed.
    Calling ``run`` with an unregistered tool name returns a safe error dict.

    Attributes:
        _tools: The registered tool name to callable mapping.
    """

    def __init__(self) -> None:
        """Initialise with an empty tool registry."""
        super().__init__()
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, tool_name: str, tool_fn: Callable[..., Any]) -> None:
        """Register a tool function under the given name.

        Args:
            tool_name: The unique tool identifier.
            tool_fn: A callable that accepts a ``Context`` and returns a result dict.
        """
        self._tools[tool_name] = tool_fn

    def run(self, tool_name: str, context: Context) -> dict[str, object]:
        """Invoke a registered tool with the current context.

        Args:
            tool_name: The name of the tool to invoke.
            context: The current run context.

        Returns:
            A dict with at minimum a ``status`` key.
            Returns ``{"status": "UNKNOWN_TOOL"}`` for unregistered names —
            never raises and never performs dynamic import.
        """
        tool_fn = self._tools.get(tool_name)
        if tool_fn is None:
            _log.warning("InMemoryToolNodeRegistry: unknown tool_name=%r", tool_name)
            return {"status": _STATUS_UNKNOWN_TOOL, "tool_name": tool_name}
        try:
            result = tool_fn(context)
        except Exception as exc:  # noqa: BLE001
            _log.error("InMemoryToolNodeRegistry: tool %r raised: %s", tool_name, exc)
            return {"status": _STATUS_ERROR, "error": str(exc)}
        else:
            if isinstance(result, dict):
                return cast("dict[str, object]", result)
            return {"status": _STATUS_SUCCESS, "result": result}
