#!/usr/bin/env python3
"""PreCompact hook for Claude Code.

No-op. This project relies on Claude Code's built-in auto-memory, so there is
no memory ledger to persist. Reads and discards the stdin event, then exits 0.
"""

from __future__ import annotations

import sys


def main() -> None:
    """Hook entry point: discard stdin and exit cleanly."""
    try:
        sys.stdin.read()
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
