"""Contract tests for the plugin registration entry point."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from hermes_attractor.plugin import register

if TYPE_CHECKING:
    from hermes_attractor.ports.hermes import ToolHandler

pytestmark = pytest.mark.contract


class _FakeContext:
    """A test double PluginContext that records tool registrations."""

    def __init__(self) -> None:
        """Initialize an empty registry."""
        super().__init__()
        self.tools: dict[str, tuple[dict[str, object], ToolHandler]] = {}

    def register_tool(self, *, name: str, schema: dict[str, object], handler: ToolHandler) -> None:
        """Record a registered tool by name."""
        self.tools[name] = (schema, handler)


def test_register_wires_both_tools() -> None:
    """Install the health and echo tools, each with a working handler."""
    ctx = _FakeContext()
    register(ctx)

    assert set(ctx.tools) == {"health", "echo"}

    health_schema, health_handler = ctx.tools["health"]
    assert health_schema["name"] == "health"

    result = json.loads(health_handler({}))
    assert result["ok"] is True
