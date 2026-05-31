"""ProfileProvisioner port: creates a Hermes profile that does not yet exist.

Pairs with :class:`~hermes_attractor.ports.profile_registry.ProfileRegistry` (which checks
existence): the provisioning use case creates exactly the profiles a pipeline names but the
host is missing, so a pipeline authored elsewhere (e.g. the self-hosting ``sp-workflow``
reference) becomes runnable. Profile creation needs host access, so it lives behind this
port (the concrete ``adapters.profile_provisioner.HermesProfileProvisioner`` wraps
``hermes_cli.profiles.create_profile``).
"""

from __future__ import annotations

from typing import Protocol


class ProfileProvisioner(Protocol):  # pragma: no cover
    """Minimal interface for creating a Hermes profile on the host."""

    def create(self, name: str) -> None:
        """Create a new profile named ``name`` on the host.

        The implementation is responsible for giving the new profile a usable model
        configuration (e.g. by cloning an existing profile). Only called for names that
        do not already exist.

        Args:
            name: The profile name to create.
        """
        ...
