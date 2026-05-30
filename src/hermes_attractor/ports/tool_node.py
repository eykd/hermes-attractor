"""ToolNodeRegistry port: resolves and invokes TOOL node deterministic work.

See: specs/001-attractor-kanban/contracts/ports.md §ToolNodeRegistry
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from hermes_attractor.domain.pipeline import Context


class ToolNodeRegistry(Protocol):  # pragma: no cover
    """Port for resolving and running TOOL node deterministic work (FR-012).

    Implementations use an **explicit allowlist** — only registered tools can
    be invoked. Dynamic import is never permitted (plan.md §Security
    §Tool-node allowlisting).
    """

    def run(self, tool_name: str, context: Context) -> Any:  # noqa: ANN401
        """Invoke a registered tool with the current context.

        Args:
            tool_name: The name of the tool to invoke.
            context: The current run context.

        Returns:
            The tool's result (dict with ``status`` and optionally
            ``context_updates``). Returns a safe error dict if the tool_name
            is not registered — never raises and never performs dynamic import.
        """
        ...
