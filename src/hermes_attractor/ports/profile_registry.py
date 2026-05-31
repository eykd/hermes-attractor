"""ProfileRegistry port: checks whether a Hermes profile exists on the host.

Run-launch validation uses this to reject a pipeline that names a profile which is not
configured on the host (FR-004 / the unknown-profile edge case), rather than silently
dispatching a card to a profile the kanban dispatcher will never spawn. Profile existence
requires host access, so it lives behind this port (the concrete
``adapters.profile_registry.HermesProfileRegistry`` wraps ``hermes_cli.profiles``).
"""

from __future__ import annotations

from typing import Protocol


class ProfileRegistry(Protocol):  # pragma: no cover
    """Minimal interface for checking Hermes profile existence."""

    def exists(self, profile: str) -> bool:
        """Return True if a profile with this name is configured on the host.

        Args:
            profile: The profile name to check (e.g. ``"planner-sonnet"``).

        Returns:
            True if the profile exists (the ``default`` profile always exists).
        """
        ...
