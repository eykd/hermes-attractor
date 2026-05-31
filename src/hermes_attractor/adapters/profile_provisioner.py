"""HermesProfileProvisioner: ProfileProvisioner backed by ``hermes_cli.profiles``.

Creates a profile by cloning an existing one's config (``create_profile(..., clone_config=
True)``), so the new profile inherits a working ``model.default`` / ``.env`` / skills and is
immediately dispatchable. With ``clone_from=None`` the source is the active profile
(``HERMES_HOME``); pass a name to clone a specific profile instead.

``hermes_cli`` is provided by the host runtime (and the ``test`` dependency-group for the
integration suite); it is imported by name via ``importlib`` so it stays out of the plugin's
runtime deps and out of static import resolution.
"""

from __future__ import annotations

import importlib

__all__ = ["HermesProfileProvisioner"]


class HermesProfileProvisioner:
    """ProfileProvisioner that creates profiles via ``hermes_cli.profiles.create_profile``.

    Attributes:
        _clone_from: Source profile to clone config from; ``None`` clones the active profile.
    """

    def __init__(self, clone_from: str | None = None) -> None:
        """Initialise with an optional clone source.

        Args:
            clone_from: Existing profile to clone config from. ``None`` (default) clones the
                active profile (``HERMES_HOME``).
        """
        super().__init__()
        self._clone_from = clone_from

    def create(self, name: str) -> None:
        """Create profile ``name`` cloning the source profile's config (model included).

        Args:
            name: The profile name to create.
        """
        profiles = importlib.import_module("hermes_cli.profiles")
        profiles.create_profile(name, clone_from=self._clone_from, clone_config=True)
