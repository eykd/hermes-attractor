#!/usr/bin/env python3
"""Pre-tool-use hook to block dangerous shell commands.

Reads a Claude Code PreToolUse(Bash) event from stdin as JSON, extracts the
bash command, and evaluates it against a set of guard rules. To BLOCK a command
the hook prints a reason to stderr and exits with code 2 (the Claude Code
blocking convention; matches agentf's pre-tool-use-bash.py). Any other outcome
exits 0 to allow the command. Parsing/runtime errors fail open (exit 0) so a
malformed event never wedges the session.

Guard rules enforced (ported from turtlebased-ts guard-rules.ts and merged with
agentf's base hook):
- Hook bypass: git --no-verify / --no-gpg-sign / -c commit.gpgsign=false
- Force push: git push --force / -f / --force-with-lease (esp. to main/master)
- git reset --hard
- git checkout . / git checkout <tree-ish> -- . (blanket discard/overwrite)
- git restore . (blanket discard; --staged is safe)
- git clean -f (delete untracked; -n / --dry-run is safe)
- git commit --amend
- git merge --squash
- git stash drop / git stash clear
- git branch -D (force-delete unmerged branch)
- Catastrophic rm -rf against /, ~, ., .., * and $HOME
"""

from __future__ import annotations

import json
import re
import sys


class GuardRule:
    """A named guard rule: a regex that blocks, with optional safe whitelist."""

    def __init__(
        self,
        name: str,
        pattern: re.Pattern[str],
        message: str,
        safe_patterns: list[re.Pattern[str]] | None = None,
    ) -> None:
        self.name = name
        self.pattern = pattern
        self.message = message
        self.safe_patterns = safe_patterns or []

    def matches(self, command: str) -> bool:
        """Return True if command is blocked by this rule (and not whitelisted)."""
        if any(sp.search(command) for sp in self.safe_patterns):
            return False
        return self.pattern.search(command) is not None


# --- _guard_rules ---------------------------------------------------------

# Rules checked against the raw (normalized) command, before quote stripping.
PRE_STRIP_RULES: list[GuardRule] = [
    GuardRule(
        name="hook-bypass",
        pattern=re.compile(
            r"git\s+.*(--no-verify|--no-gpg-sign|"
            r"commit\.gpgsign\s*=\s*false)"
        ),
        message="""BLOCKED: Hook bypass flags detected.

Prohibited: --no-verify, --no-gpg-sign, -c commit.gpgsign=false

Instead of bypassing safety checks:
- If pre-commit hook fails: Fix the linting/formatting/type errors it found
- If commit-msg fails: Write a proper conventional commit message
- If pre-push fails: Fix the issues preventing push

Fix the root problem rather than bypassing the safety mechanism.
Only use these flags when explicitly requested by the user.""",
    ),
    GuardRule(
        name="force-push",
        pattern=re.compile(
            r"git\s+push.*(--force([^-]|$)|-f(\s|$)|--force-with-lease)"
        ),
        message="""BLOCKED: Force push detected.

Force pushing rewrites remote history and can destroy teammates' work.
This is especially dangerous against main/master.

Instead:
- Use normal `git push` to push changes safely
- If rejected, pull and merge first: `git pull --rebase` then `git push`
- Only use force push when explicitly requested by the user""",
    ),
]

# Rules checked against the quote-stripped, separator-split sub-commands.
POST_STRIP_RULES: list[GuardRule] = [
    GuardRule(
        name="reset-hard",
        pattern=re.compile(r"git\s+reset\s+--hard"),
        message="""BLOCKED: git reset --hard detected.

This command discards all uncommitted changes with no recovery path.

Instead:
- Use `git stash` to save changes temporarily
- Use `git reset --soft HEAD~1` to undo a commit but keep changes
- Use `git checkout -- <file>` to discard changes in a specific file""",
    ),
    GuardRule(
        name="checkout-dot",
        pattern=re.compile(r"git\s+checkout\s+(--\s+)?\.(\s|$)"),
        message="""BLOCKED: git checkout . detected (discard all changes).

This command discards all uncommitted changes across every file.

Instead:
- Use `git checkout -- <file>` to discard changes in a specific file
- Use `git stash` to save changes temporarily
- Use `git diff` to review changes before discarding""",
    ),
    GuardRule(
        name="checkout-treeish-dot",
        pattern=re.compile(r"git\s+checkout\s+.*--\s+\.(\s|$)"),
        message="""BLOCKED: git checkout <tree-ish> -- . detected (overwrite all files).

This command overwrites all working tree files from another commit.

Instead:
- Use `git checkout <tree-ish> -- <file>` to restore a specific file
- Use `git diff <tree-ish>` to review differences first
- Use `git stash` to save current changes before restoring""",
    ),
    GuardRule(
        name="restore-dot",
        pattern=re.compile(r"git\s+restore\s+\.(\s|$)"),
        safe_patterns=[
            re.compile(r"git\s+restore\s+--staged"),
            re.compile(r"git\s+restore\s+-S"),
        ],
        message="""BLOCKED: git restore . detected (discard all changes).

This command discards all uncommitted changes across every file.

Instead:
- Use `git restore <file>` to discard changes in a specific file
- Use `git restore --staged <file>` to unstage specific files
- Use `git stash` to save changes temporarily""",
    ),
    GuardRule(
        name="clean-force",
        pattern=re.compile(r"git\s+clean\s+.*-[a-zA-Z]*f"),
        safe_patterns=[
            re.compile(r"git\s+clean\s+.*-[a-zA-Z]*n"),
            re.compile(r"git\s+clean\s+.*--dry-run"),
        ],
        message="""BLOCKED: git clean -f detected (delete untracked files).

This command permanently deletes untracked files with no recovery path.

Instead:
- Use `git clean -n` to preview what would be deleted (dry run)
- Use `git clean --dry-run` for the same preview
- Manually remove specific files you no longer need""",
    ),
    GuardRule(
        name="commit-amend",
        pattern=re.compile(r"git\s+commit\s+.*--amend"),
        message="""BLOCKED: git commit --amend detected (amending commits is prohibited).

Always create a NEW commit instead. Amending after a failed pre-commit hook
can destroy the previous commit's changes.

Instead:
- Always create a new commit for changes
- Use `git reset --soft HEAD~1` to undo a commit without losing changes
- Have the user run interactive rebase manually if reorganizing history""",
    ),
    GuardRule(
        name="merge-squash",
        pattern=re.compile(r"git\s+merge\s+.*--squash"),
        message="""BLOCKED: git merge --squash detected (squash-merging is prohibited).

Squash-merging destroys commit history and makes debugging harder.

Instead:
- Use normal `git merge` to preserve commit history
- Use `git merge --no-ff` to ensure a merge commit is created""",
    ),
    GuardRule(
        name="stash-drop",
        pattern=re.compile(r"git\s+stash\s+drop(?:\s|$)"),
        message="""BLOCKED: git stash drop detected.

This command permanently deletes a stash entry with no recovery path.

Instead:
- Use `git stash list` to review stashes before dropping
- Use `git stash apply` to apply without removing the stash
- Use `git stash pop` to apply and remove only after confirming contents""",
    ),
    GuardRule(
        name="stash-clear",
        pattern=re.compile(r"git\s+stash\s+clear(?:\s|$)"),
        message="""BLOCKED: git stash clear detected.

This command permanently deletes all stash entries with no recovery path.

Instead:
- Use `git stash list` to review stashes before clearing
- Use `git stash drop stash@{N}` to remove specific stashes one at a time
- Use `git stash apply` to recover work before removing it""",
    ),
    GuardRule(
        name="branch-force-delete",
        pattern=re.compile(r"git\s+branch\s+-D(?:\s|$)"),
        message="""BLOCKED: git branch -D detected (force-delete unmerged branch).

This deletes a branch even if it has unmerged changes, potentially losing work.

Instead:
- Use `git branch -d <branch>` to safely delete only fully-merged branches
- Use `git log <branch>` to review commits before deleting""",
    ),
    GuardRule(
        name="catastrophic-rm",
        pattern=re.compile(
            r"rm\s+(?:-[a-zA-Z]*(?:rf|fr)[a-zA-Z]*"
            r"|-[a-zA-Z]*r\s+-[a-zA-Z]*f"
            r"|-[a-zA-Z]*f\s+-[a-zA-Z]*r"
            r"|--recursive\s+--force|--force\s+--recursive)\s+"
            r"(?:\$\{HOME\}|\$HOME|\.\./|\./|~/|/|~|\.|\*)(?:\s|$)"
        ),
        message="""BLOCKED: Catastrophic rm detected -- targets system-critical path.

This command would recursively force-delete a critical path (root, home,
current directory, or all files) with no recovery.

Instead:
- Use `rm -rf <specific-directory>` to remove a known directory
- Use `ls <path>` to verify what would be affected first
- Never use rm -rf with /, ., ~, ../, *, or $HOME""",
    ),
]


# --- normalization helpers (ported from guard-rules.ts) -------------------

_WRAPPER_RE = re.compile(r"^(sudo|command|nohup|exec|time|nice)\s+")
_ENV_RE = re.compile(r"^env\s+(\w+=\S+\s+)*")
_HEREDOC_RE = re.compile(r"<<-?'?(\w+)'?\n[\s\S]*?\n\s*\1")
_DQUOTE_RE = re.compile(r'"(?:[^"\\]|\\.)*"')
_SQUOTE_RE = re.compile(r"'[^']*'")
_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||[;|])\s*")


def normalize_command(command: str) -> str:
    """Collapse line continuations and strip command wrappers (sudo/env/...)."""
    result = re.sub(r"\\\n\s*", " ", command)
    result = re.sub(r"^\\", "", result)
    prev = None
    while result != prev:
        prev = result
        result = _WRAPPER_RE.sub("", result)
        result = _ENV_RE.sub("", result)
    return result


def strip_quoted_content(command: str) -> str:
    """Replace heredocs and quoted strings with empty placeholders."""
    result = _HEREDOC_RE.sub("", command)
    result = _DQUOTE_RE.sub('""', result)
    result = _SQUOTE_RE.sub("''", result)
    return result


def split_commands(command: str) -> list[str]:
    """Split on shell separators (&&, ||, ;, |) into sub-commands."""
    return [s for s in _SPLIT_RE.split(command) if s]


def evaluate_command(command: str) -> tuple[bool, str]:
    """Evaluate a command against all guard rules.

    Returns:
        (blocked, message). blocked is True if the command should be blocked.

    """
    normalized = normalize_command(command)
    if normalized.strip() == "":
        return False, ""

    for rule in PRE_STRIP_RULES:
        if rule.matches(normalized):
            return True, rule.message

    stripped = strip_quoted_content(normalized)
    for sub in split_commands(stripped):
        for rule in POST_STRIP_RULES:
            if rule.matches(sub):
                return True, rule.message

    return False, ""


def main() -> None:
    """Hook entry point: parse stdin event and block dangerous commands."""
    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {}
        tool_input = input_data.get("tool_input")
        if not isinstance(tool_input, dict):
            tool_input = {}
        command = tool_input.get("command", "")
        if not isinstance(command, str):
            command = ""

        blocked, message = evaluate_command(command)
        if blocked:
            sys.stderr.write(message + "\n")
            sys.exit(2)  # Exit 2 = blocking error
        sys.exit(0)  # Allow the command
    except Exception:
        # Fail open: never wedge the session on a malformed/unexpected event.
        sys.exit(0)


if __name__ == "__main__":
    main()
