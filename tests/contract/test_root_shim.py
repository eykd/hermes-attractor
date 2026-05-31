"""Contract test: the repo-root plugin shim resolves ``register`` (git/directory install path).

``hermes plugins install`` moves the cloned repo to ``~/.hermes/plugins/<name>/`` and its
directory loader (``plugins.py::_load_directory_module``) imports the **root** ``__init__.py``
via ``spec_from_file_location`` and then ``getattr(module, "register")``. This guards that the
root shim loads and exposes a callable ``register`` — replicated here without a live hermes
runtime so a regression (deleting/breaking the shim, or moving it) fails fast.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

#: Repo root = tests/contract/<file> -> tests -> <root>.
_ROOT_INIT = Path(__file__).resolve().parents[2] / "__init__.py"


def test_root_shim_exposes_callable_register() -> None:
    """Loading the repo-root __init__.py (as hermes's directory loader does) yields register()."""
    assert _ROOT_INIT.is_file(), f"root plugin shim missing at {_ROOT_INIT}"

    spec = importlib.util.spec_from_file_location(
        "hermes_plugins_attractor_shim_under_test",
        _ROOT_INIT,
        submodule_search_locations=[str(_ROOT_INIT.parent)],
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    saved_path = list(sys.path)
    try:
        spec.loader.exec_module(module)  # runs the shim: src on sys.path + re-export register
    finally:
        sys.path[:] = saved_path  # the shim mutates sys.path; keep the test side-effect-free

    assert callable(getattr(module, "register", None)), "root shim must expose a callable register()"
