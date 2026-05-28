---
name: quality-review
description: "Use when: (1) Reviewing Python code for correctness and edge cases, (2) Assessing test quality against Kent Beck's Test Desiderata and 100% coverage, (3) Checking coding standards and simplicity (YAGNI), (4) Auditing CLI security."
---

# Quality Review Skill

Review Python code for correctness, test quality, standards, and CLI security.

## Review Areas

### 1. What Changed (Plain English Summary)

Describe changes in simple terms:
- What functionality was added/modified/removed?
- What problem does this solve?
- What's the user-facing impact?

### 2. Does It Work? (Correctness)

- **Edge cases**: Empty strings, None values, empty lists, boundary values
- **Error handling**: Are exceptions caught appropriately? Validation at boundaries?
- **Logic errors**: Off-by-one, wrong operators, incorrect conditionals
- **Type safety**: Do types match? Any `Any` types that should be specific?

### 3. Test Quality

Apply Kent Beck's Test Desiderata (adapted for pytest):

- **Isolated**: Tests don't depend on each other or external state
- **Composable**: Fixtures and test doubles cleanly combine
- **Fast**: No slow I/O in unit tests (< 100ms each)
- **Inspiring**: Tests make the code's purpose clear
- **Writable**: Easy to add new test cases
- **Readable**: Test intent clear from name and structure
- **Behavioral**: Test what, not how (mock sparingly)
- **Structure-insensitive**: Tests survive refactoring
- **Automated**: No manual steps
- **Specific**: Failures pinpoint the exact problem
- **Deterministic**: Same result every time
- **Predictive**: Passing tests mean production will work

**Coverage**: Must be 100% (lines + branches)

### 4. Simplicity (YAGNI)

- **Appropriate abstractions**: Not too abstract, not too concrete
- **No premature optimization**: Clear code first, optimize later if needed
- **No speculative features**: Build what's needed now
- **Minimal dependencies**: Only add libraries when justified

### 5. Python Standards

- **PEP 8**: Naming, spacing, imports (enforced by ruff)
- **Type hints**: All functions/methods fully typed (enforced by pyright strict)
- **Docstrings**: Google-style for public APIs (modules, classes, functions)
- **Line length**: 120 characters max (configured in ruff)

### 6. CLI Security

**CLI apps have different security concerns than web apps. Focus on:**

#### Command Injection
```python
# ❌ Vulnerable
import os
user_file = input("File: ")
os.system(f"cat {user_file}")  # Shell injection!

# ✅ Safe
import subprocess
subprocess.run(["cat", user_file], check=True)  # No shell
```

#### Hardcoded Secrets
```python
# ❌ Vulnerable
API_KEY = "sk-1234567890abcdef"  # Hardcoded!

# ✅ Safe
import os
API_KEY = os.environ.get("HERMES_ATTRACTOR_API_KEY")
if not API_KEY:
    raise ConfigError("HERMES_ATTRACTOR_API_KEY required")
```

#### Dangerous eval/exec
```python
# ❌ Vulnerable
user_code = input("Expression: ")
result = eval(user_code)  # Arbitrary code execution!

# ✅ Safe
# Don't use eval/exec on user input. Use safe parsers instead.
from ast import literal_eval
result = literal_eval(user_input)  # Only literals
```

#### pickle from Untrusted Sources
```python
# ❌ Vulnerable
import pickle
with open(user_file, "rb") as f:
    data = pickle.load(f)  # Can execute arbitrary code!

# ✅ Safe
import json
with open(user_file) as f:
    data = json.load(f)  # Safe serialization
```

#### Path Traversal
```python
# ❌ Vulnerable
user_path = input("File: ")
with open(f"/data/{user_path}") as f:  # ../../etc/passwd
    content = f.read()

# ✅ Safe
from pathlib import Path
base_dir = Path("/data").resolve()
file_path = (base_dir / user_path).resolve()
if not file_path.is_relative_to(base_dir):
    raise SecurityError("Path traversal detected")
```

**Not applicable to CLI apps:**
- XSS, CSRF, SQL injection (no web interface, no database)
- Session management (CLI is stateless)
- Rate limiting (local execution)

## Severity Levels

- **Critical**: Security vulnerability, data loss, crashes
- **High**: Correctness issue, missing validation, broken tests
- **Medium**: Code smell, missing types, poor naming
- **Low**: Style violation, minor optimization

## Output Format

For each finding:

```bash
npx bd create "[quality] Finding title" \
  --description "File: [path]
Line: [line-number]
Severity: [severity]
Skill: quality-review

Problem:
[detailed problem description]

Fix:
[step-by-step fix instructions]" \
  --priority [0-3] \
  --parent [epic-id]
```

If no findings: `No new findings for [file-path]`

## Deduplication

Check existing open tasks before creating:
- Compare file path + finding type
- Only report NEW issues

## References

- PEP 8: https://pep8.org
- Kent Beck Test Desiderata: https://kentbeck.github.io/TestDesiderata/
- OWASP (CLI context): Command injection, secrets, path traversal
