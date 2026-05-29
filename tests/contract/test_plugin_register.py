"""Contract tests for the plugin registration entry point."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from hermes_attractor.plugin import register

if TYPE_CHECKING:
    from hermes_attractor.ports.hermes import CommandHandler, HookHandler, ToolHandler

pytestmark = pytest.mark.contract


class _FakeContext:
    """A test double PluginContext that records tool, hook, and command registrations."""

    def __init__(self) -> None:
        """Initialize an empty registry."""
        super().__init__()
        self.tools: dict[str, tuple[dict[str, object], ToolHandler]] = {}
        self.hooks: dict[str, HookHandler] = {}
        self.commands: dict[str, CommandHandler] = {}

    def register_tool(self, *, name: str, schema: dict[str, object], handler: ToolHandler) -> None:
        """Record a registered tool by name."""
        self.tools[name] = (schema, handler)

    def register_hook(self, *, event: str, handler: HookHandler) -> None:
        """Record a registered hook handler by event name."""
        self.hooks[event] = handler

    def register_command(self, *, name: str, handler: CommandHandler) -> None:
        """Record a registered command handler by name."""
        self.commands[name] = handler


def test_register_wires_both_tools() -> None:
    """Install the health and echo tools, each with a working handler."""
    ctx = _FakeContext()
    register(ctx)

    assert set(ctx.tools) == {"health", "echo"}

    health_schema, health_handler = ctx.tools["health"]
    assert health_schema["name"] == "health"

    result = json.loads(health_handler({}))
    assert result["ok"] is True
