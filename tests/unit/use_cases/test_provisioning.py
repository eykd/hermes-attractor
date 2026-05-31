"""Unit tests for the provision_profiles use case."""

from __future__ import annotations

import pytest

from hermes_attractor.use_cases.provisioning import provision_profiles

pytestmark = pytest.mark.unit


class _FakeRegistry:
    """A test double ProfileRegistry: profiles in ``present`` exist; others do not."""

    def __init__(self, present: set[str]) -> None:
        """Store the set of existing profile names."""
        super().__init__()
        self._present = present

    def exists(self, profile: str) -> bool:
        """Return True if the profile is in the preset existing set."""
        return profile in self._present


class _FakeProvisioner:
    """A test double ProfileProvisioner recording the profiles it was asked to create."""

    def __init__(self) -> None:
        """Initialise with an empty creation log."""
        super().__init__()
        self.created: list[str] = []

    def create(self, name: str) -> None:
        """Record a creation request."""
        self.created.append(name)


def test_provision_creates_only_missing_profiles() -> None:
    """provision_profiles creates absent profiles and leaves existing ones untouched."""
    registry = _FakeRegistry(present={"existing-a", "existing-b"})
    provisioner = _FakeProvisioner()

    report = provision_profiles(
        profiles=["existing-a", "missing-x", "existing-b", "missing-y"],
        registry=registry,
        provisioner=provisioner,
    )

    assert provisioner.created == ["missing-x", "missing-y"]
    assert report == {"created": ["missing-x", "missing-y"], "existing": ["existing-a", "existing-b"]}


def test_provision_deduplicates_repeated_profile_names() -> None:
    """A profile named by several nodes is created at most once (preserving first-seen order)."""
    registry = _FakeRegistry(present=set())
    provisioner = _FakeProvisioner()

    report = provision_profiles(
        profiles=["coder", "coder", "reviewer", "coder"],
        registry=registry,
        provisioner=provisioner,
    )

    assert provisioner.created == ["coder", "reviewer"]
    assert report == {"created": ["coder", "reviewer"], "existing": []}


def test_provision_all_existing_creates_nothing() -> None:
    """When every named profile already exists, nothing is created."""
    registry = _FakeRegistry(present={"a", "b"})
    provisioner = _FakeProvisioner()

    report = provision_profiles(profiles=["a", "b"], registry=registry, provisioner=provisioner)

    assert provisioner.created == []
    assert report == {"created": [], "existing": ["a", "b"]}
