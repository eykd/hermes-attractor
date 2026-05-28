---
name: commit
description: 'Use when: (1) committing session changes, (2) creating conventional commits, (3) handling pre-commit hook failures. Python projects with ruff, pyright, and pytest.'
allowed-tools: [Bash, Read]
---

# Commit Changes

Create git commits following conventional commit format.

## Process

### 1. Review Changes

```bash
git status
git diff
```

### 2. Stage and Commit

```bash
# Stage specific files (never use -A or .)
git add file1.py file2.py src/module/

# Commit with proper format
git commit -m "feat: add new feature

- Implement core functionality
- Add comprehensive test coverage"

git log --oneline -n 3
```

## Commit Message Format

```
<type>: <subject>

<body>
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

## Line Length Rules (CRITICAL)

Conventional commits typically enforce **100-character maximum** for ALL lines:

- **Subject line**: Max 100 characters (including type and colon)
- **Body lines**: Max 100 characters **per line**

**Common mistake**: Writing long sentences that exceed 100 characters.

**Solution**: Wrap lines manually at natural break points.

### Examples

❌ **Bad** (line too long):

```bash
git commit -m "docs: update documentation with comprehensive guidance for achieving coverage goals

Add detailed instructions for writing tests that achieve 100% coverage across all project modules."
# Error: body-max-line-length
```

✅ **Good** (lines wrapped):

```bash
git commit -m "docs: update documentation with coverage guidance

Add detailed instructions for writing tests that achieve 100%
coverage across all project modules."
```

### Formatting Lists

When including lists or multiple points, keep each line under 100 chars:

```bash
git commit -m "$(cat <<'EOF'
feat: add authentication system

Implement user authentication with the following features:
- JWT token generation and validation
- Secure password hashing with bcrypt
- Session management with Redis
- Rate limiting for login attempts

All features include comprehensive test coverage.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

### Tips for Staying Under 100 Characters

1. **Break at conjunctions**: "and", "but", "or", "with"
2. **Break after punctuation**: Periods, commas, colons
3. **Use HEREDOC** for complex messages (see example above)
4. **Check line length** if commit fails with line length errors

## Important Rules

**CRITICAL - Pre-commit Hooks:**

- ❌ **NEVER EVER** use `--no-verify`, `--no-gpg-sign`, or any flag to skip hooks
- ❌ **NEVER EVER** bypass pre-commit validation in ANY way
- ✅ Pre-commit hooks are ESSENTIAL quality control and MUST ALWAYS pass
- ✅ If hooks fail, you MUST fix the underlying issue, not skip the hooks
- ✅ If you can't fix the issue, ask the user for help - DO NOT bypass hooks

**Stage files explicitly:**

- ❌ Never use `git add -A` or `git add .`
- ✅ Always specify files: `git add file1.py src/utils/`

**Message quality:**

- Use imperative mood ("add feature" not "added feature")
- Subject line: max 100 characters
- Body: explain WHY, not just WHAT

## Validation Hooks

This project has automatic validation via PostToolUse hooks:

- Ruff formatting check (`uv run ruff format --check`)
- Ruff linting (`uv run ruff check`)
- Pyright type checking (`uv run pyright`)

If validation fails during development, fix issues before committing.

## Pre-commit Workflow

1. Make changes to code
2. PostToolUse hooks run automatically (ruff format, ruff check, pyright)
3. Fix any issues reported by hooks
4. Stage files explicitly: `git add file.py`
5. Commit with conventional format
6. If pre-commit hooks fail:
   - **STOP** - do not proceed with commit
   - **INVESTIGATE** - read the error messages carefully
   - **FIX** - resolve the underlying issue (missing tools, failing tests, etc.)
   - **NEVER** use `--no-verify` or any method to skip hooks
   - If you can't fix the issue, ask the user for guidance
7. After hooks pass, verify commit was created: `git log --oneline -n 3`
8. If commit fails for other reasons, fix issues and create a NEW commit (never amend)

## Reference

- **[troubleshooting.md](references/troubleshooting.md)** — Hook failures, validation errors, commit scenarios
