#!/usr/bin/env python3
"""Status line hook for Claude Code.

Displays real-time context usage, git branch, and working directory in the
status line. Color-coded warnings at 70%, 80%, 90% thresholds. Stdlib-only;
robust to malformed/empty stdin.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_LABEL = "hermes-attractor"


def get_git_branch() -> str:
    """Get current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=1,
        )
        branch = result.stdout.strip()
        return branch or "no-git"
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return "no-git"


def get_folder_name() -> str:
    """Get current working directory name."""
    try:
        return Path.cwd().name or PROJECT_LABEL
    except Exception:
        return PROJECT_LABEL


def format_token_usage(used: int, limit: int) -> tuple[str, str]:
    """Format token usage with color coding.

    Returns:
        (formatted_string, color_name)

    """
    percentage = (used / limit * 100) if limit > 0 else 0
    thousands_used = used // 1000
    thousands_limit = limit // 1000

    if percentage >= 90:
        color = "red"
    elif percentage >= 80:
        color = "yellow"
    elif percentage >= 70:
        color = "cyan"
    else:
        color = "green"

    formatted = f"{thousands_used}k/{thousands_limit}k ({percentage:.0f}%)"
    return formatted, color


def main() -> None:
    """Generate status line content."""
    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {}
        if not isinstance(input_data, dict):
            input_data = {}
    except (json.JSONDecodeError, Exception):
        print(PROJECT_LABEL)
        return

    context_window = input_data.get("context_window")
    if not isinstance(context_window, dict):
        context_window = {}
    used_percentage = context_window.get("used_percentage", 0) or 0
    context_size = context_window.get("context_window_size", 200000) or 200000

    tokens_used = round((context_size * used_percentage) / 100)

    branch = get_git_branch()
    folder = get_folder_name()

    usage_str, usage_color = format_token_usage(tokens_used, context_size)

    cyan = "\033[36m"
    yellow = "\033[33m"
    red = "\033[31m"
    reset = "\033[0m"

    token_color = red if usage_color == "red" else yellow

    status_line = (
        f"{folder} | {cyan}[{branch}]{reset} | "
        f"{token_color}{usage_str}{reset}"
    )
    print(status_line)


if __name__ == "__main__":
    main()
