"""Provisioning use case: create the host profiles a pipeline names but is missing.

Pairs with run-launch profile-existence validation (FR-004): rather than rejecting a
pipeline whose profiles are absent, an operator/agent can provision exactly those profiles
first. Profiles that already exist are left untouched (idempotent); only the missing ones
are created.

See: specs/001-attractor-kanban/spec.md §Profile & Model Selection
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from hermes_attractor.ports.profile_provisioner import ProfileProvisioner
    from hermes_attractor.ports.profile_registry import ProfileRegistry


def provision_profiles(
    *,
    profiles: Iterable[str],
    registry: ProfileRegistry,
    provisioner: ProfileProvisioner,
) -> dict[str, list[str]]:
    """Create each named profile that does not already exist on the host.

    Deduplicates while preserving first-seen order. Profiles that already exist are reported
    as ``existing`` and never re-created (avoiding ``create_profile``'s FileExistsError).

    Args:
        profiles: The profile names a pipeline requires (e.g. ``Pipeline.resolved_worker_profiles()``
            values).
        registry: ProfileRegistry used to check existence on the host.
        provisioner: ProfileProvisioner used to create the missing profiles.

    Returns:
        A report dict with ``created`` (newly provisioned) and ``existing`` (already present)
        profile-name lists, each ordered by first appearance.
    """
    created: list[str] = []
    existing: list[str] = []
    for name in dict.fromkeys(profiles):  # dedupe, preserve order
        if registry.exists(name):
            existing.append(name)
        else:
            provisioner.create(name)
            created.append(name)
    return {"created": created, "existing": existing}
