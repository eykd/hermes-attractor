"""Hermes host boundary: the registration context a plugin's entry point receives.

NOTE: The exact Hermes runtime API is UNVERIFIED — the ``hermes`` CLI is not yet
installed (see the project's Open Items). This Protocol encodes our current assumption
about the registration surface so the hexagonal core stays decoupled and strictly typed.
Revisit ``register_tool``'s signature once the real Hermes context is available.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

ToolHandler = Callable[[dict[str, object]], str]
"""A Hermes tool handler: takes parsed tool input and returns a JSON string, never raising."""


class PluginContext(Protocol):
    """The registration context passed to a plugin's ``register`` entry point."""

    def register_tool(self, *, name: str, schema: dict[str, object], handler: ToolHandler) -> None:
        """Register a single LLM-facing tool with its JSON schema and handler."""
        ...
