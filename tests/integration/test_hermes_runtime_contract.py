"""Integration test: verify our plugin registers cleanly with the REAL Hermes runtime.

This module is skipped automatically when ``hermes_cli.plugins`` is not installed.
Run it explicitly with the hermes-agent extra:

    uv run --with hermes-agent==0.15.2 pytest tests/integration/test_hermes_runtime_contract.py -v

It must PASS under that command and SKIP under plain ``uv run pytest`` (our locked
deps do not include hermes-agent).
"""

from __future__ import annotations

from pathlib import Path

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
        "attractor_provision_profiles",
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
    """All 14 attractor tools must be accepted by the real Hermes PluginContext."""
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
    assert "post_tool_call" in manager._hooks  # noqa: SLF001
    assert any(getattr(cb, "__name__", "") == "post_tool_call_hook" for cb in manager._hooks["post_tool_call"])  # noqa: SLF001
    assert "attractor-reconcile" in manager._cli_commands  # noqa: SLF001
    command = manager._cli_commands["attractor-reconcile"]  # noqa: SLF001
    assert callable(command["setup_fn"])
    assert callable(command["handler_fn"])


def test_directory_install_path_parses_manifest_and_resolves_register() -> None:
    """Mirror ``hermes plugins install``: parse the root plugin.yaml + resolve the shim's register.

    Hermes clones the repo, reads the root plugin.yaml, moves the tree to
    ``~/.hermes/plugins/<name>/``, loads the root ``__init__.py``, and ``getattr(register)``.
    This exercises that exact path (manifest parse + directory load) against real hermes.
    """
    repo_root = Path(__file__).resolve().parents[2]
    manager = PluginManager()

    manifest = manager._parse_manifest(repo_root / "plugin.yaml", repo_root, "user", "")  # noqa: SLF001
    assert manifest is not None, "hermes failed to parse the root plugin.yaml"
    assert manifest.name == "attractor"
    assert manifest.kind == "standalone"

    module = manager._load_directory_module(manifest)  # noqa: SLF001  # imports the root __init__.py shim
    assert callable(getattr(module, "register", None)), "root shim must expose register() to the loader"
