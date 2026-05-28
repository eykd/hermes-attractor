#!/usr/bin/env python3
"""Stop hook for Claude Code.

Emits a terminal bell when Claude finishes responding. Ported from on-stop.sh:
writes the bell character ('\\a') directly to /dev/tty (bypassing stdout, which
Claude Code captures for hook response JSON). Falls back to stdout if /dev/tty
is unavailable. Reads and discards stdin; never raises; always exits 0.
"""

from __future__ import annotations

import sys


def emit_bell() -> None:
    """Write a bell character to the terminal, preferring /dev/tty."""
    try:
        with open("/dev/tty", "w") as tty:
            tty.write("\a")
            tty.flush()
        return
    except Exception:
        pass
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        pass


def main() -> None:
    """Hook entry point: discard stdin, ring the bell, exit cleanly."""
    try:
        sys.stdin.read()
    except Exception:
        pass
    emit_bell()
    sys.exit(0)


if __name__ == "__main__":
    main()
