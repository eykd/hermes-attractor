"""Unit tests for the PluginContext port Protocol."""

from __future__ import annotations

import inspect

import pytest

from hermes_attractor.ports.hermes import PluginContext

pytestmark = pytest.mark.unit


def test_plugin_context_has_register_hook() -> None:
    """PluginContext Protocol must declare a register_hook method."""
    assert hasattr(PluginContext, "register_hook"), "PluginContext is missing register_hook — add it to ports/hermes.py"
    assert callable(PluginContext.register_hook), "PluginContext.register_hook must be callable"


def test_plugin_context_has_register_command() -> None:
    """PluginContext Protocol must declare a register_command method."""
    assert hasattr(PluginContext, "register_command"), (
        "PluginContext is missing register_command — add it to ports/hermes.py"
    )
    assert callable(PluginContext.register_command), "PluginContext.register_command must be callable"


def test_register_hook_signature() -> None:
    """register_hook must accept event and handler keyword arguments."""
    sig = inspect.signature(PluginContext.register_hook)
    params = set(sig.parameters.keys()) - {"self"}
    assert "event" in params, "register_hook must have an 'event' parameter"
    assert "handler" in params, "register_hook must have a 'handler' parameter"


def test_register_command_signature() -> None:
    """register_command must accept name and handler keyword arguments."""
    sig = inspect.signature(PluginContext.register_command)
    params = set(sig.parameters.keys()) - {"self"}
    assert "name" in params, "register_command must have a 'name' parameter"
    assert "handler" in params, "register_command must have a 'handler' parameter"
