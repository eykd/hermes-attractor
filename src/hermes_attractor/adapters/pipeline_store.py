"""Git-backed PipelineStore adapter with path confinement and local-only fallback.

This adapter handles all git operations via subprocess with shell=False. It confines
all file operations to the configured repo root and rejects unsafe spec_ids.

See: specs/001-attractor-kanban/contracts/ports.md §PipelineStore
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path  # noqa: TC003  # Path is used in runtime annotations

from hermes_attractor.domain.exceptions import PipelineValidationError, ValidationIssue

#: Regex for a safe spec_id component: alphanumerics, underscores, and hyphens only.
_SAFE_SPEC_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_spec_id(spec_id: str, repo_root: Path) -> Path:
    r"""Validate and resolve a spec_id to a safe path within the repo root.

    Rejection rules (plan.md §Security §Path/repo):
    - Empty spec_id.
    - Contains ``..`` segments.
    - Contains path separators (``/`` or ``\``).
    - Is an absolute path.
    - Contains characters outside ``[A-Za-z0-9_-]``.
    - Resolved path is outside repo_root (confinement check).

    Args:
        spec_id: The raw spec_id provided by the caller.
        repo_root: The repository root directory.

    Returns:
        The resolved absolute Path for the ``<spec_id>.dot`` file.

    Raises:
        PipelineValidationError: If the spec_id is unsafe.
    """
    if not spec_id:
        msg = "spec_id must not be empty"
        raise PipelineValidationError(
            issues=[ValidationIssue(element_id="spec_id", reason=msg)],
            message="Invalid spec_id",
        )
    if ".." in spec_id:
        msg = f"spec_id {spec_id!r} contains '..' (path traversal)"
        raise PipelineValidationError(
            issues=[ValidationIssue(element_id="spec_id", reason=msg)],
            message="Invalid spec_id",
        )
    if "/" in spec_id or "\\" in spec_id:
        msg = f"spec_id {spec_id!r} contains a path separator"
        raise PipelineValidationError(
            issues=[ValidationIssue(element_id="spec_id", reason=msg)],
            message="Invalid spec_id",
        )
    _win_drive_prefix_len = 2
    if spec_id.startswith("/") or (len(spec_id) >= _win_drive_prefix_len and spec_id[1] == ":"):
        msg = f"spec_id {spec_id!r} is an absolute path"  # pragma: no cover
        raise PipelineValidationError(  # pragma: no cover
            issues=[ValidationIssue(element_id="spec_id", reason=msg)],  # pragma: no cover
            message="Invalid spec_id",  # pragma: no cover
        )  # pragma: no cover
    if not _SAFE_SPEC_ID_RE.match(spec_id):
        msg = f"spec_id {spec_id!r} contains characters outside [A-Za-z0-9_-]"
        raise PipelineValidationError(
            issues=[ValidationIssue(element_id="spec_id", reason=msg)],
            message="Invalid spec_id",
        )
    resolved = (repo_root / f"{spec_id}.dot").resolve()
    repo_root_resolved = repo_root.resolve()
    if not str(resolved).startswith(str(repo_root_resolved)):  # pragma: no cover  # defense against symlink escape
        msg = f"Resolved path {resolved} is outside repo_root {repo_root_resolved}"
        raise PipelineValidationError(
            issues=[ValidationIssue(element_id="spec_id", reason=msg)],
            message="Path confinement violation",
        )
    return resolved


def _git(args: list[str], cwd: Path) -> None:
    """Run a git command in the given working directory.

    Args:
        args: Git command arguments (no shell interpolation).
        cwd: The working directory for the git command.

    Raises:
        PipelineValidationError: If the git command fails.
    """
    result = subprocess.run(  # noqa: S603  # intentional: args are fixed git subcommands, no untrusted input
        ["git", *args],  # noqa: S607  # intentional: git binary by name, no shell
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    if result.returncode != 0:  # pragma: no cover  # defensive: git failures are infra errors
        msg = f"git {' '.join(args)} failed: {result.stderr.strip()}"
        raise PipelineValidationError(
            issues=[ValidationIssue(element_id="git", reason=msg)],
            message="Git command failed",
        )


class GitPipelineStore:
    """PipelineStore adapter backed by a git-tracked directory.

    All git invocations use subprocess with shell=False. All file operations
    are confined to repo_root (path traversal is rejected before any I/O).

    Attributes:
        repo_root: The root directory for pipeline storage and git operations.
    """

    def __init__(self, repo_root: Path) -> None:
        """Initialise with the given repo root directory.

        Args:
            repo_root: The directory to store pipeline .dot files and manage as a git repo.
        """
        super().__init__()
        self.repo_root = repo_root

    def ensure_repo(self) -> None:
        """Initialize a git repository in repo_root if one does not already exist.

        If ``.git`` is already present this method is a no-op.
        """
        if not (self.repo_root / ".git").exists():
            _git(["init", "--"], self.repo_root)
            # Configure a local user for commits (needed in clean environments).
            _git(["config", "user.email", "attractor@hermes.local"], self.repo_root)
            _git(["config", "user.name", "Hermes Attractor"], self.repo_root)

    def save(self, spec_id: str, dot: str) -> None:
        """Write the DOT string to <spec_id>.dot and git-commit it.

        Args:
            spec_id: The pipeline identifier (safe chars only, no path traversal).
            dot: The raw DOT string to persist.

        Raises:
            PipelineValidationError: If spec_id is unsafe or git operations fail.
        """
        dot_path = _validate_spec_id(spec_id, self.repo_root)
        self.ensure_repo()
        _ = dot_path.write_text(dot, encoding="utf-8")
        _git(["add", "--", str(dot_path.name)], self.repo_root)
        _git(
            ["commit", "-m", f"attractor: save pipeline {spec_id}", "--", str(dot_path.name)],
            self.repo_root,
        )

    def load(self, spec_id: str) -> str:
        """Read and return the DOT text for the given spec_id.

        Args:
            spec_id: The pipeline identifier (safe chars only).

        Returns:
            The raw DOT string.

        Raises:
            PipelineValidationError: If spec_id is unsafe or the file does not exist.
        """
        dot_path = _validate_spec_id(spec_id, self.repo_root)
        if not dot_path.exists():
            msg = f"Pipeline {spec_id!r} not found at {dot_path}"
            raise PipelineValidationError(
                issues=[ValidationIssue(element_id=spec_id, reason=msg)],
                message="Pipeline not found",
            )
        return dot_path.read_text(encoding="utf-8")
