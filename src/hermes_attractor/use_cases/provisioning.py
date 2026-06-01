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
    from collections.abc import Iterable, Mapping

    from hermes_attractor.ports.profile_provisioner import ProfileProvisioner
    from hermes_attractor.ports.profile_registry import ProfileRegistry

#: Recognized model tiers, low→high. A profile whose name ends in ``-<tier>`` is mapped to the
#: corresponding model via the ``models`` map at provisioning time (e.g. ``plan-high`` → high).
MODEL_TIERS: tuple[str, ...] = ("low", "medium", "high")


def tier_for_profile(name: str) -> str | None:
    """Return the model tier encoded in a profile name's ``-<tier>`` suffix, or ``None``.

    Role+tier profiles name their model tier as a suffix (``coder-high``, ``analyst-medium``,
    ``orchestrator-low``); non-model profiles (``human``, ``constitution-loader``) carry no
    tier and return ``None``.

    Args:
        name: The profile name.

    Returns:
        ``"high" | "medium" | "low"`` if the name ends with that tier suffix, else ``None``.
    """
    for tier in MODEL_TIERS:
        if name.endswith(f"-{tier}"):
            return tier
    return None


def provision_profiles(
    *,
    profiles: Iterable[str],
    registry: ProfileRegistry,
    provisioner: ProfileProvisioner,
    models: Mapping[str, str] | None = None,
) -> dict[str, list[str]]:
    """Create each named profile that does not already exist on the host.

    Deduplicates while preserving first-seen order. Profiles that already exist are reported
    as ``existing`` and never re-created (avoiding ``create_profile``'s FileExistsError). When
    ``models`` is given, a profile whose name carries a tier suffix (``tier_for_profile``) is
    created with that tier's model; profiles with no tier (or no entry in ``models``) inherit
    the cloned base profile's model.

    Args:
        profiles: The profile names a pipeline requires (e.g. ``Pipeline.resolved_worker_profiles()``
            values).
        registry: ProfileRegistry used to check existence on the host.
        provisioner: ProfileProvisioner used to create the missing profiles.
        models: Optional ``{tier: model}`` map (e.g. ``{"high": "...", "medium": "...", "low": "..."}``)
            used to set ``model.default`` per tier on newly created profiles.

    Returns:
        A report dict with ``created`` (newly provisioned) and ``existing`` (already present)
        profile-name lists, each ordered by first appearance.
    """
    created: list[str] = []
    existing: list[str] = []
    for name in dict.fromkeys(profiles):  # dedupe, preserve order
        if registry.exists(name):
            existing.append(name)
            continue
        model: str | None = None
        if models:
            tier = tier_for_profile(name)
            if tier is not None:
                model = models.get(tier)
        provisioner.create(name, model=model)
        created.append(name)
    return {"created": created, "existing": existing}
