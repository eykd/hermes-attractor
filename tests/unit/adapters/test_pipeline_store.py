"""Unit tests for the PipelineStore port and git adapter (RED phase for M1).

Tests fail until ports/pipeline_store.py and adapters/pipeline_store.py are implemented.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from hermes_attractor.adapters.pipeline_store import (
    GitPipelineStore,
    _validate_spec_id,  # pyright: ignore[reportPrivateUsage]
)
from hermes_attractor.domain.exceptions import PipelineValidationError, RepoPathConfinementError
from hermes_attractor.ports.pipeline_store import PipelineStore

pytestmark = pytest.mark.unit

_SAMPLE_DOT = "digraph test { start [shape=Mdiamond]; exit [shape=Msquare]; start -> exit; }"


def test_pipeline_store_protocol_has_load_save_ensure_repo() -> None:
    """PipelineStore Protocol must declare load, save, and ensure_repo methods."""
    assert hasattr(PipelineStore, "load")
    assert hasattr(PipelineStore, "save")
    assert hasattr(PipelineStore, "ensure_repo")
    assert callable(PipelineStore.load)
    assert callable(PipelineStore.save)
    assert callable(PipelineStore.ensure_repo)


def test_git_pipeline_store_ensure_repo_initializes_git(tmp_path: Path) -> None:
    """GitPipelineStore.ensure_repo initializes a git repo in an empty directory."""
    store = GitPipelineStore(repo_root=tmp_path)
    store.ensure_repo()
    assert (tmp_path / ".git").exists()


def test_git_pipeline_store_save_writes_dot_file(tmp_path: Path) -> None:
    """GitPipelineStore.save writes a .dot file to the repo root."""
    store = GitPipelineStore(repo_root=tmp_path)
    store.ensure_repo()
    store.save("my_pipeline", _SAMPLE_DOT)
    assert (tmp_path / "my_pipeline.dot").exists()


def test_git_pipeline_store_save_commits_dot_file(tmp_path: Path) -> None:
    """GitPipelineStore.save git-commits the .dot file."""
    store = GitPipelineStore(repo_root=tmp_path)
    store.ensure_repo()
    store.save("my_pipeline", _SAMPLE_DOT)

    result = subprocess.run(
        ["git", "-C", str(tmp_path), "log", "--oneline", "--", "my_pipeline.dot"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip(), "Expected at least one git commit for my_pipeline.dot"


def test_git_pipeline_store_load_returns_dot_text(tmp_path: Path) -> None:
    """GitPipelineStore.load returns the previously saved DOT text."""
    store = GitPipelineStore(repo_root=tmp_path)
    store.ensure_repo()
    store.save("my_pipeline", _SAMPLE_DOT)
    loaded = store.load("my_pipeline")
    assert "start" in loaded
    assert "exit" in loaded


def test_git_pipeline_store_rejects_dotdot_in_spec_id(tmp_path: Path) -> None:
    """GitPipelineStore raises PipelineValidationError for spec_id containing '..'."""
    store = GitPipelineStore(repo_root=tmp_path)
    with pytest.raises(PipelineValidationError):
        store.save("../escape", _SAMPLE_DOT)


def test_git_pipeline_store_rejects_path_separator_in_spec_id(tmp_path: Path) -> None:
    """GitPipelineStore raises PipelineValidationError for spec_id containing '/'."""
    store = GitPipelineStore(repo_root=tmp_path)
    with pytest.raises(PipelineValidationError):
        store.save("subdir/pipeline", _SAMPLE_DOT)


def test_git_pipeline_store_rejects_absolute_spec_id(tmp_path: Path) -> None:
    """GitPipelineStore raises PipelineValidationError for an absolute spec_id."""
    store = GitPipelineStore(repo_root=tmp_path)
    with pytest.raises(PipelineValidationError):
        store.save("/absolute/path", _SAMPLE_DOT)


def test_git_pipeline_store_rejects_empty_spec_id(tmp_path: Path) -> None:
    """GitPipelineStore raises PipelineValidationError for an empty spec_id."""
    store = GitPipelineStore(repo_root=tmp_path)
    with pytest.raises(PipelineValidationError):
        store.save("", _SAMPLE_DOT)


def test_git_pipeline_store_rejects_special_chars_in_spec_id(tmp_path: Path) -> None:
    """GitPipelineStore raises PipelineValidationError for spec_id with special chars."""
    store = GitPipelineStore(repo_root=tmp_path)
    with pytest.raises(PipelineValidationError):
        store.save("my pipeline!", _SAMPLE_DOT)


def test_git_pipeline_store_load_raises_when_file_missing(tmp_path: Path) -> None:
    """GitPipelineStore.load raises PipelineValidationError when the .dot file does not exist."""
    store = GitPipelineStore(repo_root=tmp_path)
    store.ensure_repo()
    with pytest.raises(PipelineValidationError):
        _ = store.load("nonexistent_pipeline")


def test_git_pipeline_store_raises_on_load_missing_file(tmp_path: Path) -> None:
    """GitPipelineStore.load raises on a valid spec_id with no matching .dot file."""
    store = GitPipelineStore(repo_root=tmp_path)
    store.ensure_repo()
    with pytest.raises(PipelineValidationError):
        _ = store.load("another_nonexistent")


def test_from_env_returns_cwd_store_when_no_repo_path() -> None:
    """GitPipelineStore.from_env with no repo_path returns a store rooted at the base."""
    store = GitPipelineStore.from_env(None)
    assert store.repo_root == Path.cwd()


def test_from_env_returns_cwd_store_when_empty_repo_path() -> None:
    """GitPipelineStore.from_env with an empty string returns a store rooted at the base."""
    store = GitPipelineStore.from_env("")
    assert store.repo_root == Path.cwd()


def test_from_env_rejects_absolute_repo_path() -> None:
    """GitPipelineStore.from_env raises RepoPathConfinementError for an absolute path."""
    with pytest.raises(RepoPathConfinementError, match="must be relative"):
        _ = GitPipelineStore.from_env("/tmp/evil")  # noqa: S108


def test_from_env_rejects_dotdot_repo_path() -> None:
    """GitPipelineStore.from_env raises RepoPathConfinementError for paths with '..' segments."""
    with pytest.raises(RepoPathConfinementError, match="must not contain"):
        _ = GitPipelineStore.from_env("../escape")


def test_from_env_rejects_symlink_escaping_base(tmp_path: Path) -> None:
    """GitPipelineStore.from_env rejects a symlinked path resolving outside the base.

    Exercises the post-resolution is_relative_to guard that catches symlink-based escapes
    slipping past the '..' and is_absolute early checks.
    """
    outside = tmp_path.parent / "outside_dir"
    outside.mkdir()
    link = tmp_path / "escape_link"
    link.symlink_to(outside)

    old_env = os.environ.get("ATTRACTOR_REPO_BASE")
    try:
        os.environ["ATTRACTOR_REPO_BASE"] = str(tmp_path)
        with pytest.raises(RepoPathConfinementError, match="outside allowed base"):
            _ = GitPipelineStore.from_env("escape_link")
    finally:
        if old_env is None:
            _ = os.environ.pop("ATTRACTOR_REPO_BASE", None)
        else:
            os.environ["ATTRACTOR_REPO_BASE"] = old_env


def test_from_env_accepts_relative_path_within_base(tmp_path: Path) -> None:
    """GitPipelineStore.from_env accepts a relative path within the allowed base."""
    base = tmp_path.parent
    subdir_name = tmp_path.name

    old_env = os.environ.get("ATTRACTOR_REPO_BASE")
    try:
        os.environ["ATTRACTOR_REPO_BASE"] = str(base)
        store = GitPipelineStore.from_env(subdir_name)
        assert store.repo_root == tmp_path.resolve()
    finally:
        if old_env is None:
            _ = os.environ.pop("ATTRACTOR_REPO_BASE", None)
        else:
            os.environ["ATTRACTOR_REPO_BASE"] = old_env


def test_from_env_uses_attractor_repo_base_env_var(tmp_path: Path) -> None:
    """GitPipelineStore.from_env uses ATTRACTOR_REPO_BASE env var as the confinement base."""
    old_env = os.environ.get("ATTRACTOR_REPO_BASE")
    try:
        os.environ["ATTRACTOR_REPO_BASE"] = str(tmp_path)
        store = GitPipelineStore.from_env(None)
        assert store.repo_root == tmp_path.resolve()
    finally:
        if old_env is None:
            _ = os.environ.pop("ATTRACTOR_REPO_BASE", None)
        else:
            os.environ["ATTRACTOR_REPO_BASE"] = old_env


def test_validate_spec_id_rejects_sibling_dir_prefix_bypass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Path confinement uses is_relative_to, not startswith, so a sibling like /repo-evil is rejected.

    Regression test for the prefix-match weakness: str('/repo-evil').startswith(str('/repo'))
    would have incorrectly returned True and allowed escape to a sibling directory.
    is_relative_to('/repo-evil', '/repo') correctly returns False.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Simulate a symlink-escape scenario where resolve() returns a path outside repo_root
    # but which *is* a string-prefix match for repo_root (the classic bug).
    # We achieve this by monkeypatching Path.resolve so the resolved path lands
    # in a sibling directory named with a shared prefix (e.g. "repo-evil").
    sibling = tmp_path / "repo-evil"
    sibling.mkdir()
    evil_dot = sibling / "mypipeline.dot"

    original_resolve = Path.resolve

    def _patched_resolve(self: Path, **kwargs: object) -> Path:
        """Return the evil sibling path for the target file, real path otherwise."""
        result: Path = original_resolve(self, **kwargs)  # type: ignore[call-arg]
        if self.name == "mypipeline.dot":
            return evil_dot
        return result

    monkeypatch.setattr(Path, "resolve", _patched_resolve)

    with pytest.raises(PipelineValidationError, match="Path confinement violation"):
        _ = _validate_spec_id("mypipeline", repo_root)
