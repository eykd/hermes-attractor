"""Unit tests for the profile provisioner's config.yaml model writer.

``_set_model_default`` is pure file/YAML I/O (PyYAML is provided by the hermes runtime, present
in the test env), so it is unit-testable without the hermes profile machinery.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import pytest

from hermes_attractor.adapters.profile_provisioner import (
    _set_model_default,  # pyright: ignore[reportPrivateUsage]
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

_yaml = importlib.import_module("yaml")


def test_set_model_default_preserves_other_keys(tmp_path: Path) -> None:
    """Setting model.default rewrites only the model default, preserving other config keys."""
    cfg = tmp_path / "config.yaml"
    _ = cfg.write_text("model:\n  default: old/model\n  provider: prov\ntoolsets:\n  - kanban\n")

    _set_model_default(tmp_path, "new/model")

    data = _yaml.safe_load(cfg.read_text())
    assert data["model"]["default"] == "new/model"
    assert data["model"]["provider"] == "prov"  # sibling model key preserved
    assert data["toolsets"] == ["kanban"]  # other top-level keys preserved


def test_set_model_default_creates_config_when_absent(tmp_path: Path) -> None:
    """When no config.yaml exists (clone source had none), it is created with the model default."""
    _set_model_default(tmp_path, "new/model")

    cfg = tmp_path / "config.yaml"
    assert cfg.exists()
    data = _yaml.safe_load(cfg.read_text())
    assert data["model"]["default"] == "new/model"
