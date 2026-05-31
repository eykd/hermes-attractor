"""Hermes Attractor: a Hermes Agent plugin built on a hexagonal core."""

from __future__ import annotations

try:
    from hermes_attractor._version import __version__
except ImportError:  # pragma: no cover - _version.py is build-generated; absent only in a raw git clone
    # The git-install path (`hermes plugins install`) clones source without building, so the
    # hatch-vcs version file is missing. Fall back so plugin load does not hard-fail.
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
