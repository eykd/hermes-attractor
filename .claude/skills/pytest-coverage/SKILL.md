---
name: pytest-coverage
description: "Use when: (1) Setting up coverage tooling, (2) Analyzing coverage reports to identify gaps, (3) Deciding when to use pragma: no cover/no branch, (4) Configuring exclusion patterns, (5) Questions about line vs branch coverage, (6) Setting up CI/CD coverage enforcement."
---

# pytest-coverage

Achieve 100% test coverage in Python projects with pytest-cov and coverage.py.

## Quick Setup

```bash
uv add --group=test pytest pytest-cov coverage
```

Minimal `pyproject.toml`:

```toml
[tool.coverage.run]
branch = true
source = ["src"]

[tool.coverage.report]
fail_under = 100
show_missing = true
```

Run: `pytest --cov=src --cov-branch --cov-report=term-missing`

## Line vs Branch Coverage

**Always enable branch coverage** (`branch = true`). Line coverage misses conditional paths.

```python
def get_status(value):
    status = "unknown"
    if value > 0:
        status = "positive"
    return status
```

Line coverage: 100% with just `test_get_status(5)`.
Branch coverage: Requires testing both `value > 0` (True) AND `value <= 0` (False).

## The Two Pragma Comments

| Pragma | Effect |
|--------|--------|
| `# pragma: no cover` | Excludes line AND its entire block |
| `# pragma: no branch` | Line covered, but missing branch path acceptable |

## When to Use `# pragma: no cover`

Appropriate for code that genuinely cannot or should not be tested:

```python
# 1. Debug-only code
if settings.DEBUG:  # pragma: no cover
    print(f"Debug: {data}")

# 2. __repr__ methods (debugging aids)
def __repr__(self):  # pragma: no cover
    return f"User({self.name!r})"

# 3. Abstract methods
@abstractmethod
def process(self, data):  # pragma: no cover
    raise NotImplementedError

# 4. Platform-specific (can't test on CI)
if sys.platform == "win32":  # pragma: no cover
    return _windows_impl()

# 5. Main entry points
if __name__ == "__main__":  # pragma: no cover
    main()

# 6. Defensive unreachable code (after validation)
if already_validated_nonzero and b == 0:  # pragma: no cover
    raise RuntimeError("Validation failed")
```

**Never use for**: Untested business logic, testable error paths, "I'll test later" code.

## When to Use `# pragma: no branch`

Use when a branch **intentionally** never takes one path:

```python
# 1. Loops that exit via break/return
while timeout_not_reached:  # pragma: no branch
    if event_occurred():
        return True
    sleep(0.1)

# 2. Retry loops that should succeed
for attempt in range(max_retries):  # pragma: no branch
    try:
        return fetch(url)
    except RequestError:
        if attempt == max_retries - 1:
            raise

# 3. Feature flags always on/off in tests
if FEATURE_FLAGS["enhanced"]:  # pragma: no branch
    result = enhance(result)
```

## Configuration-Based Exclusions

Prefer config patterns over inline pragmas. See `references/config-patterns.md` for complete examples.

```toml
[tool.coverage.report]
exclude_also = [
    "def __repr__",
    "def __str__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@(abc\\.)?abstractmethod",
]
```

Use `exclude_also` (not `exclude_lines`) to preserve default `pragma: no cover` pattern.

## Anti-Patterns

1. **Excluding untested business logic** — Write tests instead
2. **Confusing no cover with no branch** — `no cover` excludes entire block
3. **Over-using pragmas** — Error paths should usually be tested
4. **Excluding to inflate numbers** — Defeats the purpose

## CI Enforcement

```yaml
- name: Test with coverage
  run: pytest --cov=src --cov-branch --cov-fail-under=100
```

## Decision Tree

```
Is this code genuinely untestable?
├─ No → Write tests
└─ Yes → Why?
    ├─ Platform-specific → # pragma: no cover
    ├─ Debug/development only → # pragma: no cover
    ├─ Abstract method → Config pattern or pragma
    ├─ __repr__/__str__ → Config pattern
    ├─ Main entry point → Config pattern
    ├─ Loop that always breaks → # pragma: no branch
    └─ Defensive unreachable → # pragma: no cover (with comment)
```

## Reference Files

- `references/config-patterns.md` — Complete configuration examples
- `references/pragma-examples.md` — Detailed pragma usage patterns
