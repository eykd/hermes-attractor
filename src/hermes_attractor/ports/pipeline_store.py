"""PipelineStore port: storage and retrieval of pipeline DOT files.

See: specs/001-attractor-kanban/contracts/ports.md §PipelineStore
"""

from __future__ import annotations

from typing import Protocol


class PipelineStore(Protocol):
    """Port for loading and saving pipeline DOT files (FR-003).

    Implementations (adapters) handle git-tracked storage with a local-only
    repo fallback. Only adapters import pathlib, subprocess, or git concerns.
    """

    def load(self, spec_id: str) -> str:
        """Load and return the DOT text for the given spec_id.

        Args:
            spec_id: The pipeline identifier (maps to ``<spec_id>.dot``).

        Returns:
            The raw DOT string for the pipeline.

        Raises:
            PipelineValidationError: If spec_id is invalid or the file does not exist.
        """
        ...

    def save(self, spec_id: str, dot: str) -> None:
        """Write the DOT text for the given spec_id and git-commit it.

        Args:
            spec_id: The pipeline identifier (maps to ``<spec_id>.dot``).
            dot: The raw DOT string to persist.

        Raises:
            PipelineValidationError: If spec_id is unsafe (path traversal, absolute path, etc.)
        """
        ...

    def ensure_repo(self) -> None:
        """Initialize a git repository if one does not already exist.

        This is a no-op if ``.git`` is already present.
        """
        ...
