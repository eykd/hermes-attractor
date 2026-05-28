---
name: security-review
description: Review Python code for security vulnerabilities and best practices. Use when (1) reviewing code for security issues, (2) auditing authentication/secret handling, (3) checking for injection (SQL, command, template) vulnerabilities, (4) reviewing deserialization and path-traversal risks, (5) validating input handling, (6) assessing password hashing and secrets management, (7) reviewing subprocess and file I/O, or (8) general security hardening of Python web/CLI applications.
---

# Security Review Skill

Systematic security review of Python code following OWASP guidelines and defense-in-depth principles. Use `ruff`'s `S` (flake8-bandit) ruleset as a fast first-pass signal, then apply the deeper checks in the references below.

## Audience: Non-Technical Managers

**CRITICAL**: Write for non-technical managers using plain English (6th-grade reading level).

**Style Requirements:**

- **Report problems only** - never acknowledge what's done well or include praise
- **Target 30-second scan time** - compress findings to 2-3 lines maximum
- **Use plain language** - explain technical terms briefly (e.g., "SQL injection - inserting malicious database commands")
- **Focus on business impact** - data breach, financial loss, reputation damage
- **Be concise** - one-sentence problem, one-line fix

## Review Process

1. **Run the fast signal**: `uv run ruff check --select S` flags many bandit-style issues (subprocess, pickle, hardcoded passwords, `yaml.load`, weak hashes, `eval`/`exec`). Treat hits as leads, not gospel.
2. **Identify security surface**: secret handling, user input, subprocess/shell, deserialization, file paths, database queries, external APIs.
3. **Check each domain** using the references below.
4. **Prioritize findings**: Critical > High > Medium > Low.
5. **Provide actionable fixes** with code examples.
6. **File remediation tasks** in beads (see "Creating Remediation Tasks").

## Security Domains

### Secrets & Authentication

See [references/auth-security.md](references/auth-security.md) for password hashing (Argon2id via `argon2-cffi`), token generation (`secrets`), constant-time comparison (`hmac.compare_digest`), and secrets management (`os.environ`, never hard-coded).

### Injection (SQL / Command / Template)

See [references/injection-security.md](references/injection-security.md) for parameterized queries, `subprocess` without `shell=True`, and Jinja2 autoescaping / avoiding `eval`/`exec`.

### Deserialization & Untrusted Data

See [references/deserialization-security.md](references/deserialization-security.md) for `pickle`/`yaml.load` risks, `path traversal`, and safe parsing.

### Input Validation & Request Metadata

See [references/data-validation.md](references/data-validation.md) for server-side validation, size limits, and request metadata checks.

### Quick Checklist

See [references/checklist.md](references/checklist.md) for a rapid security audit.

## Critical Patterns to Flag

### Always Critical

```python
# SQL injection - string formatting into a query
cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")          # ❌
cursor.execute("SELECT * FROM users WHERE id = '%s'" % user_id)        # ❌

# Command injection - shell=True with interpolated input
subprocess.run(f"convert {filename} out.png", shell=True)              # ❌

# Insecure deserialization
pickle.loads(untrusted_bytes)                                          # ❌
yaml.load(untrusted_text)                                              # ❌ (use yaml.safe_load)

# Arbitrary code execution
eval(user_input)                                                       # ❌
exec(user_input)                                                       # ❌

# Weak password hashing
hashlib.md5(password.encode()).hexdigest()                             # ❌
hashlib.sha256(password.encode()).hexdigest()                          # ❌ (no salt, fast)

# Hardcoded secrets
API_KEY = "sk-abc123..."                                               # ❌
```

### Always High

```python
# Timing-vulnerable secret comparison
if token == stored_token:                                              # ❌ (use hmac.compare_digest)

# Path traversal - joining user input into a filesystem path
open(os.path.join(base_dir, user_filename))                            # ❌ (validate/resolve first)

# Unvalidated redirect / SSRF - fetching a user-supplied URL
httpx.get(request.params["url"])                                       # ❌

# Disabled TLS verification
httpx.get(url, verify=False)                                           # ❌
requests.get(url, verify=False)                                        # ❌
```

## Secure Patterns

### Parameterized Query

```python
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))         # ✅ (sqlite3 / DB-API)
```

### Subprocess Without a Shell

```python
subprocess.run(["convert", filename, "out.png"], check=True)           # ✅ (argv list, no shell)
```

### Constant-Time Compare

```python
import hmac

hmac.compare_digest(token, stored_token)                               # ✅
```

### Safe Path Resolution

```python
from pathlib import Path

base = Path("/srv/uploads").resolve()
target = (base / user_filename).resolve()
if not target.is_relative_to(base):                                    # ✅ rejects ../ traversal
    raise ValueError("invalid path")
```

### Token Generation

```python
import secrets

session_id = secrets.token_urlsafe(32)                                 # ✅ 256 bits
```

## Review Output Format

**COMPRESSED FORMAT** (2-3 lines per finding):

```markdown
## Security Review

### Critical

- src/hermes_attractor/adapters/user_repo.py:45: SQL injection - user input formatted into query string
  Fix: use a parameterized query: `cursor.execute("SELECT * FROM users WHERE email = ?", (email,))`

- src/hermes_attractor/adapters/hasher.py:12: Weak password hashing - using sha256 without a salt
  Fix: switch to Argon2id via `argon2-cffi` (`PasswordHasher().hash(password)`)

### High

- src/hermes_attractor/adapters/runner.py:23: Command injection - `subprocess.run(..., shell=True)` with user input
  Fix: pass an argv list and drop `shell=True`

### Medium

- src/hermes_attractor/use_cases/login.py:34: Timing-vulnerable token comparison with `==`
  Fix: use `hmac.compare_digest(token, stored)`
```

**DO NOT include:**

- ~~"None found"~~ sections - omit sections with no issues
- ~~Praise or positive feedback~~ - focus exclusively on problems
- ~~Lengthy explanations~~ - keep to 2-3 lines per finding

## Tooling Signal

`ruff`'s `S` ruleset maps to many of these checks. Useful rule IDs to know:

| Rule    | Catches                                          |
| ------- | ------------------------------------------------ |
| `S101`  | `assert` used outside tests                      |
| `S105/6/7` | Hardcoded password strings/args               |
| `S301`  | `pickle` / unsafe deserialization                |
| `S307`  | Use of `eval`                                    |
| `S324`  | Insecure hash (md5/sha1) for security context    |
| `S501`  | TLS verification disabled (`verify=False`)       |
| `S506`  | Unsafe `yaml.load`                               |
| `S602/3/4/7` | `subprocess` with shell / partial paths     |
| `S608`  | Possible SQL injection via string building       |

A clean `uv run ruff check --select S` is necessary but **not sufficient** — bandit-style rules miss logic-level issues (auth bypass, SSRF, mass assignment). Always do the manual pass.

## Creating Remediation Tasks

When findings exist, file beads tasks so the fixes are tracked (see the `beads-task-chains` skill, Type D):

```bash
# Testable fix → Red/Green/Refactor chain under a remediation parent
REMEDIATE_ID=$(br create "Remediate: SQL injection in user_repo" \
  --parent "$IMPL_ID" --priority 0 --add-label security \
  --description "[security] CRITICAL src/hermes_attractor/adapters/user_repo.py:45 — user input formatted into SQL. Fix with parameterized query. Done when: failing test added, fix applied, ruff/pyright clean." \
  --silent)

# Non-testable (config/docs) → flat task
br create "[security] Disable TLS verify bypass in http client" \
  --parent "$IMPL_ID" --priority 1 --add-label security \
  --description "..."
```

Map severity to priority: Critical→0, High→1, Medium→2, Low→3.

## Related Skills

This skill works together with:

- **quality-review**: code correctness, test quality, general code standards
- **architecture-review**: layer boundaries, dependency direction
- **error-handling-patterns**: error disclosure prevention, safe error responses
- **beads-task-chains**: structuring remediation fixes as Type D task chains
- **pii-redaction**: ensuring secrets/PII never reach logs

When reviewing code, use multiple skills for comprehensive analysis:

1. **Security review** (this skill): secrets, injection, deserialization, input validation
2. **Architecture review**: layer violations, dependency issues
3. **Quality review**: error handling, test coverage, code standards
