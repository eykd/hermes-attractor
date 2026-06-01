"""Unit tests for the provision_profiles use case."""

from __future__ import annotations

import pytest

from hermes_attractor.use_cases.provisioning import provision_profiles, tier_for_profile

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("plan-high", "high"),
        ("analyst-medium", "medium"),
        ("orchestrator-low", "low"),
        ("coder", None),
        ("human", None),
        ("constitution-loader", None),
        ("high", None),  # bare tier without the "-" suffix is not a tier
    ],
)
def test_tier_for_profile(name: str, expected: str | None) -> None:
    """tier_for_profile reads the -high/-medium/-low suffix; everything else is None."""
    assert tier_for_profile(name) == expected


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
        self.models: dict[str, str | None] = {}

    def create(self, name: str, *, model: str | None = None) -> None:
        """Record a creation request and the model it was created with."""
        self.created.append(name)
        self.models[name] = model


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


def test_provision_sets_tier_model_from_models_map() -> None:
    """With a models map, tiered profiles get their tier's model; non-tiered profiles get None."""
    registry = _FakeRegistry(present=set())
    provisioner = _FakeProvisioner()
    models = {"high": "prov/strong", "medium": "prov/mid", "low": "prov/cheap"}

    _ = provision_profiles(
        profiles=["plan-high", "analyst-medium", "orchestrator-low", "human"],
        registry=registry,
        provisioner=provisioner,
        models=models,
    )

    assert provisioner.models == {
        "plan-high": "prov/strong",
        "analyst-medium": "prov/mid",
        "orchestrator-low": "prov/cheap",
        "human": None,  # no tier suffix -> keeps the cloned base model
    }


def test_provision_tier_without_models_map_leaves_model_unset() -> None:
    """Without a models map, even tiered profiles are created with model=None (clone base)."""
    registry = _FakeRegistry(present=set())
    provisioner = _FakeProvisioner()

    _ = provision_profiles(profiles=["plan-high"], registry=registry, provisioner=provisioner)

    assert provisioner.models == {"plan-high": None}


def test_provision_tier_missing_from_models_map_leaves_model_unset() -> None:
    """A tiered profile whose tier is absent from the models map gets model=None."""
    registry = _FakeRegistry(present=set())
    provisioner = _FakeProvisioner()

    _ = provision_profiles(
        profiles=["plan-high"],
        registry=registry,
        provisioner=provisioner,
        models={"medium": "prov/mid"},  # no "high" entry
    )

    assert provisioner.models == {"plan-high": None}
