#!/usr/bin/env python3
"""SessionStart hook for Claude Code.

Prints a short context note to stdout (which Claude Code injects into the
session): the current git branch and, if `br` (beads_rust) is on PATH, a count
of ready tasks. Deliberately MINIMAL -- this project relies on Claude Code's
built-in auto-memory, so there is no ledger or file persistence here.

Reads and ignores the stdin event; never fails the hook (always exits 0).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys


def get_git_branch() -> str | None:
    """Return the current git branch, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        branch = result.stdout.strip()
        return branch or None
    except Exception:
        return None


def get_ready_task_count() -> int | None:
    """Return the count of `br ready` tasks, or None if br is unavailable."""
    if shutil.which("br") is None:
        return None
    try:
        result = subprocess.run(
            ["br", "ready"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        return len(lines)
    except Exception:
        return None


def main() -> None:
    """Hook entry point: emit a short context note to stdout."""
    try:
        raw = sys.stdin.read()
        # Parse to stay contract-compliant; the payload is not otherwise used.
        if raw.strip():
            json.loads(raw)
    except Exception:
        pass

    notes: list[str] = []

    branch = get_git_branch()
    if branch:
        notes.append(f"Git branch: {branch}")

    ready = get_ready_task_count()
    if ready is not None:
        notes.append(f"Ready tasks (br ready): {ready}")

    if notes:
        print(" | ".join(notes))

    sys.exit(0)


if __name__ == "__main__":
    main()
