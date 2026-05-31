"""Root plugin shim for the ``hermes plugins install`` (git/directory) load path.

Hermes's git installer clones this repo to ``~/.hermes/plugins/attractor/`` and its
directory loader imports **this** file as the plugin module, then calls ``register(ctx)``.
The real implementation lives under ``src/``; this shim makes that importable (the git
installer adds no dependencies / no ``pip install``) and re-exports ``register``.

The pip entry-point path does **not** use this shim — it loads ``hermes_attractor.plugin``
directly via the ``hermes_agent.plugins`` entry point.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from hermes_attractor.plugin import register  # noqa: E402  # deferred until sys.path is set

__all__ = ["register"]
