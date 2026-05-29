"""Unit tests for the PluginContext port Protocol."""

from __future__ import annotations

import inspect

import pytest

from hermes_attractor.ports.hermes import PluginContext

pytestmark = pytest.mark.unit


def test_plugin_context_has_register_tool() -> None:
    """PluginContext Protocol must declare a register_tool method."""
    assert hasattr(PluginContext, "register_tool"), "PluginContext is missing register_tool"
    assert callable(PluginContext.register_tool), "PluginContext.register_tool must be callable"


def test_plugin_context_has_register_hook() -> None:
    """PluginContext Protocol must declare a register_hook method."""
    assert hasattr(PluginContext, "register_hook"), "PluginContext is missing register_hook"
    assert callable(PluginContext.register_hook), "PluginContext.register_hook must be callable"


def test_plugin_context_has_register_cli_command() -> None:
    """PluginContext Protocol must declare a register_cli_command method."""
    assert hasattr(PluginContext, "register_cli_command"), (
        "PluginContext is missing register_cli_command — add it to ports/hermes.py"
    )
    assert callable(PluginContext.register_cli_command), "PluginContext.register_cli_command must be callable"


def test_register_hook_signature() -> None:
    """register_hook must accept hook_name and callback parameters (verified vs hermes-agent 0.15.2)."""
    sig = inspect.signature(PluginContext.register_hook)
    params = set(sig.parameters.keys()) - {"self"}
    assert "hook_name" in params, "register_hook must have a 'hook_name' parameter"
    assert "callback" in params, "register_hook must have a 'callback' parameter"


def test_register_cli_command_signature() -> None:
    """register_cli_command must accept name, help, and setup_fn parameters."""
    sig = inspect.signature(PluginContext.register_cli_command)
    params = set(sig.parameters.keys()) - {"self"}
    assert "name" in params, "register_cli_command must have a 'name' parameter"
    assert "help" in params, "register_cli_command must have a 'help' parameter"
    assert "setup_fn" in params, "register_cli_command must have a 'setup_fn' parameter"


def test_register_tool_signature() -> None:
    """register_tool must accept name, toolset, schema, handler parameters."""
    sig = inspect.signature(PluginContext.register_tool)
    params = set(sig.parameters.keys()) - {"self"}
    assert "name" in params, "register_tool must have a 'name' parameter"
    assert "toolset" in params, "register_tool must have a 'toolset' parameter"
    assert "schema" in params, "register_tool must have a 'schema' parameter"
    assert "handler" in params, "register_tool must have a 'handler' parameter"
