"""Unit tests for the ToolNodeRegistry port and InMemoryToolNodeRegistry adapter (RED phase M6 US7).

Tests fail until ports/tool_node.py and adapters/tool_node_registry.py are implemented.
"""

from __future__ import annotations

import pytest

from hermes_attractor.adapters.tool_node_registry import InMemoryToolNodeRegistry
from hermes_attractor.domain.pipeline import Context
from hermes_attractor.ports.tool_node import ToolNodeRegistry

pytestmark = pytest.mark.unit


def test_tool_node_registry_protocol_has_run_method() -> None:
    """ToolNodeRegistry Protocol must declare a run method."""
    assert hasattr(ToolNodeRegistry, "run")
    assert callable(ToolNodeRegistry.run)


def test_in_memory_registry_run_known_tool_invokes_it() -> None:
    """InMemoryToolNodeRegistry.run invokes the registered tool and returns its result."""
    ctx = Context(data={"input": "data"})

    def my_tool(context: Context) -> dict[str, object]:
        """A simple test tool."""
        return {"status": "SUCCESS", "context_updates": {"output": "processed"}}

    registry = InMemoryToolNodeRegistry()
    registry.register("my_tool", my_tool)

    result = registry.run("my_tool", ctx)

    assert result is not None
    assert result.get("status") == "SUCCESS"


def test_in_memory_registry_run_tool_returning_non_dict_wraps_result() -> None:
    """InMemoryToolNodeRegistry.run wraps non-dict tool results in a status dict."""
    ctx = Context(data={})

    def value_tool(context: Context) -> str:
        """A tool that returns a plain string."""
        return "42"

    registry = InMemoryToolNodeRegistry()
    registry.register("value_tool", value_tool)

    result = registry.run("value_tool", ctx)

    assert result.get("status") == "SUCCESS"
    assert result.get("result") == "42"


def test_in_memory_registry_run_tool_that_raises_returns_safe_error() -> None:
    """InMemoryToolNodeRegistry.run returns a safe error when the tool raises."""
    ctx = Context(data={})

    def failing_tool(context: Context) -> dict[str, object]:
        """A tool that raises an exception."""
        msg = "tool broke"
        raise RuntimeError(msg)

    registry = InMemoryToolNodeRegistry()
    registry.register("broken_tool", failing_tool)

    result = registry.run("broken_tool", ctx)

    assert result is not None
    assert result.get("status") == "ERROR"
    assert "tool broke" in str(result.get("error", ""))


def test_in_memory_registry_run_unknown_tool_returns_safe_error() -> None:
    """InMemoryToolNodeRegistry.run returns a safe error for an unknown tool (never dynamic import)."""
    registry = InMemoryToolNodeRegistry()
    ctx = Context(data={})

    result = registry.run("nonexistent_tool", ctx)

    # Must not raise — returns an error Outcome.
    assert result is not None
    # The result should indicate failure, not success.
    status = result.get("status") if isinstance(result, dict) else None  # type: ignore[union-attr]
    assert status in ("ERROR", "FAIL", "UNKNOWN_TOOL"), f"Expected error status for unknown tool, got: {result}"
