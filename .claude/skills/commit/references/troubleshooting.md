# Commit Troubleshooting

## PostToolUse Hook Failures

The project uses PostToolUse hooks that run after Edit/Write operations. These hooks validate code quality before you commit.

### Ruff Format Errors

```bash
# Check what needs formatting
uv run ruff format --check

# Auto-fix formatting issues
uv run ruff format .
```

### Ruff Lint Errors

```bash
# Check for linting issues
uv run ruff check

# Auto-fix many linting issues
uv run ruff check --fix

# For complex issues, manually fix and retry
```

### Pyright Type Errors

```bash
# Check types (strict mode)
uv run pyright

# Fix type errors manually
# Common fixes:
# - Add type annotations
# - Use proper generic types
# - Handle Optional/None values correctly (pyright strict reports them)
```

### Test Failures

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_module.py

# Run with coverage
uv run pytest --cov

# Fix failing tests and retry commit
```

## Commit Message Validation

### Common Line Length Errors

**Error: Line too long**

One or more lines exceed 100 characters (if using commitlint or similar).

Fix: Manually wrap long lines at natural break points:

```bash
# Before (fails)
git commit -m "feat: add feature

This is a very long line that exceeds one hundred characters and will cause the commit to fail."

# After (passes)
git commit -m "feat: add feature

This is a very long line that exceeds one hundred characters and
will cause the commit to fail."
```

**Other validation rules:**

- Ensure commit message follows conventional commit format
- Check that type is valid (feat, fix, docs, etc.)
- Subject line should be lowercase (after type:)
- No period at end of subject line
- Subject line max 100 characters

## Python Project Commit Scenarios

### New Feature with Tests

```
feat: add [feature name]

- Implement [component/function]
- Add comprehensive test coverage
- Update type annotations
```

### Bug Fix

```
fix: resolve [issue description]

- Fix [specific problem]
- Add regression test
```

### Configuration Changes

```
chore: update [tool] configuration

- Adjust [setting] for [reason]
- Impact: [description]
```

### Dependency Updates

```
chore: update dependencies

- Update [package] to v[version]
- Reason: [security/feature/bugfix]
```

### Refactoring

```
refactor: restructure [component]

- Extract [functionality] into separate module
- Improve [aspect] without changing behavior
- All tests pass
```

### Documentation

```
docs: update [documentation type]

- Add [section/topic]
- Clarify [concept]
```

## Pre-commit Hook Failures

**CRITICAL**: If git pre-commit hooks fail, you MUST fix the issue. NEVER use `--no-verify` or any method to skip hooks.

### Tool Not Found Errors (e.g., "Executable `uv` not found")

If pre-commit hooks fail because they can't find `uv` or other tools:

1. **STOP** - Do not bypass hooks with `--no-verify`
2. **INVESTIGATE** - The tool may not be in the PATH used by pre-commit
3. **ASK THE USER** - Request guidance on how to fix the PATH or environment issue
4. **POSSIBLE SOLUTIONS** (user should decide):
   - Update `.pre-commit-config.yaml` to use full path to tools
   - Set up pre-commit to use the correct Python environment
   - Install tools in pre-commit's isolated environment
   - Disable problematic hooks (only if user approves)

**Example error:**

```
uv-lock..................................................................Failed
- hook id: uv-lock
- exit code: 1

Executable `uv` not found
```

**What NOT to do:**

```bash
# ❌ NEVER DO THIS
git commit --no-verify -m "message"
```

**What to do:**

```bash
# ✅ Stop and ask the user
# "The pre-commit hooks are failing because uv isn't found.
# How should I fix this? Should I update the pre-commit config?"
```

## Environment Issues

### Missing Dependencies

If hooks fail because tools aren't installed:

```bash
# Install dev dependencies
uv sync --group dev

# Install test dependencies (includes ruff, pyright)
uv sync --group test

# Install all dependencies
uv sync --all-groups
```

### Git Hook Configuration

This project may use both:
- **PostToolUse hooks** (Claude Code feature) - run after Edit/Write
- **Git pre-commit hooks** (via `.pre-commit-config.yaml`) - run during commit

To check configurations:

```bash
# PostToolUse hooks (Claude Code)
cat .claude/settings.json

# Git pre-commit hooks
cat .pre-commit-config.yaml
```

## Recovery from Failed Commits

**CRITICAL**: Always create NEW commits after failures, never amend:

```bash
# ❌ Wrong - this modifies the PREVIOUS commit
git add file.py
git commit --amend

# ✅ Correct - creates a NEW commit
git add file.py
git commit -m "fix: correct issue from previous attempt

- Address [specific problem]
- All validation passes"
```

**Why**: After a hook failure, the commit did NOT happen. Using `--amend` would modify the previous successful commit, potentially losing work.
