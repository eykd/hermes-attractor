"""HermesToolClient port: the minimal interface for calling Hermes tools.

Both the KanbanBoard and EventLog adapters depend on this contract to invoke
the Hermes tool surface.  Defining the Protocol here (in ``ports/``) rather
than inline in each adapter keeps the dependency arrow pointing inward and
makes the contract referenceable from outside the adapters without importing
the adapter itself.

The concrete runtime implementation is
``adapters.runtime_tool_client.RuntimeToolClient``, which wraps the verified
``tools.registry.registry.dispatch(name, args) -> json_str`` seam (hermes-agent 0.15.2)
and JSON-decodes the response. See
``specs/001-attractor-kanban/research-hermes-kanban.md`` §Phase 1 (A).
"""

from __future__ import annotations

from typing import Any, Protocol


class HermesToolClient(Protocol):  # pragma: no cover
    """Minimal interface for invoking a Hermes tool by name.

    Adapters that wrap the Hermes tool surface should accept this type in
    their constructors so that callers remain decoupled from any concrete
    client implementation.
    """

    def call(self, tool_name: str, **kwargs: Any) -> Any:  # noqa: ANN401
        """Invoke a Hermes tool by name with keyword arguments.

        Args:
            tool_name: The Hermes tool identifier (e.g. ``"kanban_create"``).
            **kwargs: Tool-specific arguments forwarded to the Hermes runtime.

        Returns:
            The tool's response payload.  Shape depends on the specific tool.
        """
        ...
