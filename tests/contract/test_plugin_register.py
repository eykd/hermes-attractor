"""Contract tests for the plugin registration entry point."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from hermes_attractor.plugin import register

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.contract

_ALL_TOOL_NAMES = frozenset(
    {
        "health",
        "echo",
        "attractor_create_graph",
        "attractor_add_node",
        "attractor_remove_node",
        "attractor_add_edge",
        "attractor_remove_edge",
        "attractor_set_stylesheet",
        "attractor_validate",
        "attractor_summary",
        "attractor_run",
        "attractor_status",
        "attractor_result",
    }
)


class _FakeContext:
    """A test double PluginContext that records tool, hook, and CLI-command registrations."""

    def __init__(self) -> None:
        """Initialize an empty registry."""
        super().__init__()
        self.tools: dict[str, tuple[str, dict[str, object], Callable[..., str]]] = {}
        self.hooks: dict[str, Callable[..., None]] = {}
        self.cli_commands: dict[str, dict[str, object]] = {}

    def register_tool(  # noqa: PLR0913
        self,
        name: str,
        toolset: str,
        schema: dict[str, object],
        handler: Callable[..., str],
        check_fn: Callable[..., object] | None = None,
        requires_env: list[str] | None = None,
        is_async: bool = False,
        description: str = "",
        emoji: str = "",
        override: bool = False,
    ) -> None:
        """Record a registered tool by name, toolset, schema, and handler."""
        self.tools[name] = (toolset, schema, handler)

    def register_hook(self, hook_name: str, callback: Callable[..., None]) -> None:
        """Record a registered hook callback by hook name."""
        self.hooks[hook_name] = callback

    def register_cli_command(
        self,
        name: str,
        help: str,  # noqa: A002
        setup_fn: Callable[..., None],
        handler_fn: Callable[..., None] | None = None,
        description: str = "",
    ) -> None:
        """Record a registered CLI command by name."""
        self.cli_commands[name] = {
            "name": name,
            "help": help,
            "setup_fn": setup_fn,
            "handler_fn": handler_fn,
            "description": description,
        }


def test_register_wires_all_thirteen_tools() -> None:
    """Register all 13 attractor tools, each with correct toolset and schema."""
    ctx = _FakeContext()
    register(ctx)

    assert set(ctx.tools) == _ALL_TOOL_NAMES


def test_each_tool_registered_with_attractor_toolset() -> None:
    """Every registered tool must declare toolset 'attractor'."""
    ctx = _FakeContext()
    register(ctx)

    for name, (toolset, _schema, _handler) in ctx.tools.items():
        assert toolset == "attractor", f"{name!r} has toolset {toolset!r}, expected 'attractor'"


def test_each_schema_has_parameters_key() -> None:
    """Each schema must use 'parameters' (not 'input_schema') per the verified API."""
    ctx = _FakeContext()
    register(ctx)

    for name, (_toolset, schema, _handler) in ctx.tools.items():
        assert "parameters" in schema, f"{name!r} schema missing 'parameters' key"
        assert "input_schema" not in schema, f"{name!r} schema has legacy 'input_schema' key"


def test_each_schema_name_matches_tool_name() -> None:
    """Each schema's 'name' field must match the registered tool name."""
    ctx = _FakeContext()
    register(ctx)

    for name, (_toolset, schema, _handler) in ctx.tools.items():
        assert schema["name"] == name, f"Schema name {schema['name']!r} does not match registered name {name!r}"


def test_health_handler_returns_ok_json() -> None:
    """Health handler must return a JSON object with ok=True."""
    ctx = _FakeContext()
    register(ctx)

    _toolset, _schema, handler = ctx.tools["health"]
    result = json.loads(handler({}))
    assert result["ok"] is True


def test_handler_tolerates_runtime_kwargs() -> None:
    """Handlers must silently accept extra runtime kwargs like task_id and session_id."""
    ctx = _FakeContext()
    register(ctx)

    _toolset, _schema, handler = ctx.tools["health"]
    # Simulate how the Hermes runtime calls handlers: with extra kwargs.
    result = json.loads(handler({}, task_id="t-123", session_id="s-456"))
    assert result["ok"] is True


def test_register_registers_reconcile_hooks() -> None:
    """Part B registers the live-advance (post_tool_call) and recovery (on_session_start) hooks."""
    ctx = _FakeContext()
    register(ctx)

    assert set(ctx.hooks) == {"post_tool_call", "on_session_start"}
    assert callable(ctx.hooks["post_tool_call"])
    assert callable(ctx.hooks["on_session_start"])


def test_register_registers_attractor_reconcile_cli_command() -> None:
    """Part B registers the attractor-reconcile CLI command with setup and handler fns."""
    ctx = _FakeContext()
    register(ctx)

    assert set(ctx.cli_commands) == {"attractor-reconcile"}
    command = ctx.cli_commands["attractor-reconcile"]
    assert command["name"] == "attractor-reconcile"
    assert callable(command["setup_fn"])
    assert callable(command["handler_fn"])
    assert isinstance(command["help"], str)
    assert command["help"]
