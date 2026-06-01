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
from pathlib import Path
from typing import cast

__all__ = ["HermesProfileProvisioner"]


def _set_model_default(profile_dir: Path, model: str) -> None:
    """Write ``model.default = model`` into a profile's ``config.yaml``, preserving other keys.

    Re-serializes the config via PyYAML (provided by the hermes runtime); imported by name so
    the module stays import-clean and static analysis does not resolve it.

    Args:
        profile_dir: The profile directory (contains ``config.yaml``).
        model: The model identifier to set as ``model.default``.
    """
    yaml = importlib.import_module("yaml")
    config_path = profile_dir / "config.yaml"
    raw: object = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else None
    data: dict[str, object] = cast("dict[str, object]", raw) if isinstance(raw, dict) else {}
    model_cfg = data.get("model")
    merged: dict[str, object] = cast("dict[str, object]", model_cfg) if isinstance(model_cfg, dict) else {}
    merged["default"] = model
    data["model"] = merged
    _ = config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


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

    def create(self, name: str, *, model: str | None = None) -> None:
        """Create profile ``name`` cloning the source profile's config; optionally set its model.

        Args:
            name: The profile name to create.
            model: Optional model identifier to write as the new profile's ``model.default``
                (overriding the cloned base model). When ``None`` the cloned model is kept.
        """
        profiles = importlib.import_module("hermes_cli.profiles")
        profile_dir = profiles.create_profile(name, clone_from=self._clone_from, clone_config=True)
        if model:
            _set_model_default(Path(profile_dir), model)
