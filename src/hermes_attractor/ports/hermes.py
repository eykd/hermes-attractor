"""Hermes host boundary: the registration context a plugin's entry point receives.

NOTE: The exact Hermes runtime API is UNVERIFIED — the ``hermes`` CLI is not yet
installed (see the project's Open Items). This Protocol encodes our current assumption
about the registration surface so the hexagonal core stays decoupled and strictly typed.
Revisit all method signatures once the real Hermes context is available.

The entry-point group has been reconciled to ``hermes_agent.plugins`` (research R-EP).
Hook and command registration shapes are UNVERIFIED (research D2); reconcile at
integration.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

ToolHandler = Callable[[dict[str, object]], str]
"""A Hermes tool handler: takes parsed tool input and returns a JSON string, never raising."""

HookHandler = Callable[[dict[str, object]], None]
"""A Hermes hook handler: called with event payload, returns nothing."""

CommandHandler = Callable[[dict[str, object]], str]
"""A Hermes CLI command handler: takes parsed arguments and returns a result string."""


class PluginContext(Protocol):
    """The registration context passed to a plugin's ``register`` entry point."""

    def register_tool(self, *, name: str, schema: dict[str, object], handler: ToolHandler) -> None:
        """Register a single LLM-facing tool with its JSON schema and handler."""
        ...

    def register_hook(self, *, event: str, handler: HookHandler) -> None:
        """Register a hook handler for a lifecycle event (e.g. ``post_tool_call``).

        NOTE: The exact event name strings and payload shapes are UNVERIFIED against the
        installed Hermes runtime. Reconcile at integration.
        """
        ...

    def register_command(self, *, name: str, handler: CommandHandler) -> None:
        """Register a CLI command handler (e.g. ``reconcile``).

        NOTE: The exact command dispatch protocol is UNVERIFIED against the installed
        Hermes runtime. Reconcile at integration.
        """
        ...
