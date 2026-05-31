"""HermesProfileRegistry: ProfileRegistry backed by ``hermes_cli.profiles``.

Concrete :class:`~hermes_attractor.ports.profile_registry.ProfileRegistry` that delegates
to the verified ``hermes_cli.profiles.profile_exists`` (0.15.2): the ``default`` profile
always exists; every other name resolves to a ``HERMES_HOME/profiles/<name>`` directory.

``hermes_cli`` is provided by the host runtime (and the ``test`` dependency-group for the
integration suite); it is imported by name via ``importlib`` so it stays out of the
plugin's runtime deps and out of static import resolution.
"""

from __future__ import annotations

import importlib

__all__ = ["HermesProfileRegistry"]


class HermesProfileRegistry:
    """ProfileRegistry that checks existence via ``hermes_cli.profiles.profile_exists``."""

    def exists(self, profile: str) -> bool:
        """Return True if the named profile is configured on the host.

        Args:
            profile: The profile name to check.

        Returns:
            True if the profile exists (``default`` always exists).
        """
        profiles = importlib.import_module("hermes_cli.profiles")
        return bool(profiles.profile_exists(profile))
