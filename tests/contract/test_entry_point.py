"""Contract test: the ``hermes_agent.plugins`` entry point resolves to a registerable module.

Replicates hermes-agent's loader (``hermes_cli/plugins.py``: ``_load_entrypoint_module`` does
``ep.load()``, then ``_load_plugin`` does ``getattr(module, "register")``). If the entry point
points at the ``register`` *function* (``module:register``) instead of the *module*, ``ep.load()``
returns the function and the ``getattr`` lookup yields ``None`` — so hermes silently registers
nothing. This guard catches that packaging regression without a live hermes runtime.
"""

from __future__ import annotations

import importlib.metadata

import pytest

pytestmark = pytest.mark.contract

_GROUP = "hermes_agent.plugins"


def test_attractor_entry_point_resolves_to_module_with_register() -> None:
    """The 'attractor' entry point must load to a module whose ``register`` is callable."""
    attractor = [ep for ep in importlib.metadata.entry_points().select(group=_GROUP) if ep.name == "attractor"]
    assert attractor, f"no 'attractor' entry point found in group {_GROUP!r}"

    loaded = attractor[0].load()  # mirrors hermes _load_entrypoint_module
    register = getattr(loaded, "register", None)  # mirrors hermes _load_plugin
    assert callable(register), (
        "the entry point must reference the module (not the register function): "
        f"ep.load() returned {type(loaded).__name__}, which exposes no callable register()"
    )
