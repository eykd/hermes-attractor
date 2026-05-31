"""Integration test: verify our plugin registers cleanly with the REAL Hermes runtime.

This module is skipped automatically when ``hermes_cli.plugins`` is not installed.
Run it explicitly with the hermes-agent extra:

    uv run --with hermes-agent==0.15.2 pytest tests/integration/test_hermes_runtime_contract.py -v

It must PASS under that command and SKIP under plain ``uv run pytest`` (our locked
deps do not include hermes-agent).
"""

from __future__ import annotations

import pytest

hermes_plugins = pytest.importorskip("hermes_cli.plugins")

from hermes_cli.plugins import PluginContext, PluginManager, PluginManifest  # noqa: E402

from hermes_attractor.plugin import register  # noqa: E402

pytestmark = pytest.mark.integration

_EXPECTED_TOOL_NAMES = frozenset(
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


def _make_context() -> tuple[PluginContext, PluginManager]:
    """Construct a real PluginContext backed by a real PluginManager.

    Returns:
        A ``(ctx, manager)`` pair ready for plugin registration.
    """
    manager = PluginManager()
    manifest = PluginManifest(
        name="attractor",
        version="0.1.0",
        description="Attractor plugin (integration test)",
        author="",
        requires_env=[],
        provides_tools=list(_EXPECTED_TOOL_NAMES),
        provides_hooks=[],
        source="pip",
        path=None,
        kind="standalone",
        key="attractor",
    )
    ctx = PluginContext(manifest, manager)
    return ctx, manager


def test_register_wires_all_tools_in_real_context() -> None:
    """All 13 attractor tools must be accepted by the real Hermes PluginContext."""
    ctx, manager = _make_context()
    register(ctx)

    # Access via the public API: _plugin_tool_names is the only way to inspect
    # which tools were plugin-registered (no public accessor in 0.15.2).
    registered: set[str] = manager._plugin_tool_names  # noqa: SLF001
    assert registered == _EXPECTED_TOOL_NAMES


def test_register_wires_reconcile_hook_and_cli_in_real_context() -> None:
    """register() registers the on_session_start hook + attractor-reconcile CLI command."""
    ctx, manager = _make_context()
    register(ctx)

    # PluginManager stores hooks per name and CLI commands by name (0.15.2 internals).
    assert "on_session_start" in manager._hooks  # noqa: SLF001
    assert any(getattr(cb, "__name__", "") == "reconcile_hook" for cb in manager._hooks["on_session_start"])  # noqa: SLF001
    assert "attractor-reconcile" in manager._cli_commands  # noqa: SLF001
    command = manager._cli_commands["attractor-reconcile"]  # noqa: SLF001
    assert callable(command["setup_fn"])
    assert callable(command["handler_fn"])
