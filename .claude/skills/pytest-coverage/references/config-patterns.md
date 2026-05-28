# Coverage Configuration Patterns

Complete configuration examples for pytest-cov and coverage.py.

## pyproject.toml (Recommended)

```toml
[project]
name = "my-project"
version = "1.0.0"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "--cov=src",
    "--cov-branch",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-fail-under=100",
]

[tool.coverage.run]
branch = true
source = ["src"]
omit = [
    "*/migrations/*",
    "*/__pycache__/*",
    "*/conftest.py",
]

[tool.coverage.report]
fail_under = 100
show_missing = true
skip_covered = false
exclude_also = [
    # Debugging
    "def __repr__",
    "def __str__",

    # Defensive programming
    "raise AssertionError",
    "raise NotImplementedError",

    # Non-runnable
    "if __name__ == .__main__.:",
    "if 0:",
    "if False:",

    # Type checking
    "if TYPE_CHECKING:",
    "@overload",

    # Abstract
    "@(abc\\.)?abstractmethod",
    "^\\s*\\.\\.\\.$",

    # Protocols
    "class .*\\bProtocol\\):",
]

[tool.coverage.html]
directory = "htmlcov"
show_contexts = true
```

## .coveragerc (Alternative)

```ini
[run]
branch = True
source = src
omit =
    */migrations/*
    */__pycache__/*

[report]
fail_under = 100
show_missing = True
exclude_also =
    def __repr__
    def __str__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @(abc\.)?abstractmethod

[html]
directory = htmlcov
```

## pytest.ini (Standalone)

```ini
[pytest]
testpaths = tests
addopts = --cov=src --cov-branch --cov-report=term-missing --cov-report=html --cov-fail-under=100
```

## Command-Line Options

```bash
# Basic coverage
pytest --cov=src --cov-report=term-missing

# With branch coverage
pytest --cov=src --cov-branch --cov-report=term-missing

# Multiple reports
pytest --cov=src --cov-report=term-missing --cov-report=html --cov-report=xml

# Fail under threshold
pytest --cov=src --cov-fail-under=100

# Omit patterns
pytest --cov=src --cov-omit="*/migrations/*,*/tests/*"

# Specify config file
pytest --cov=src --cov-config=.coveragerc
```

## Key Configuration Options

### [tool.coverage.run]

| Option | Purpose |
|--------|---------|
| `branch = true` | Enable branch coverage (recommended) |
| `source = ["src"]` | Directories to measure |
| `omit = [...]` | File patterns to exclude |
| `dynamic_context = "test_function"` | Track which test covers what |

### [tool.coverage.report]

| Option | Purpose |
|--------|---------|
| `fail_under = N` | Fail if coverage < N% |
| `show_missing = true` | Show line numbers of missing coverage |
| `skip_covered = true` | Hide 100% covered files in report |
| `exclude_also = [...]` | Regex patterns to exclude (adds to defaults) |
| `exclude_lines = [...]` | Regex patterns to exclude (replaces defaults) |

### exclude_also vs exclude_lines

- **`exclude_also`**: Adds patterns to defaults (preserves `pragma: no cover`)
- **`exclude_lines`**: Replaces all defaults (must re-add `pragma: no cover`)

**Always use `exclude_also`.**

## Django-Specific Configuration

```toml
[tool.coverage.run]
branch = true
source = ["myapp"]
omit = [
    "*/migrations/*",
    "*/admin.py",
    "**/settings/*.py",
    "manage.py",
    "*/wsgi.py",
    "*/asgi.py",
]

[tool.coverage.report]
exclude_also = [
    "def __repr__",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@(abc\\.)?abstractmethod",
    # Django-specific
    "class Meta:",
    "class .*\\bConfig\\):",
]
```

## GitHub Actions CI

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync --group test

      - name: Run tests with coverage
        run: uv run pytest --cov=src --cov-branch --cov-fail-under=100

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          fail_ci_if_error: true
```

## Partial Branch Exclusions

For branch-specific exclusions (not line exclusions):

```toml
[tool.coverage.report]
partial_branches_always = [
    "pragma: no branch",
]
```

Built-in partial branch exclusions:
- `while True:`
- `while 1:`
- `if 0:`
- `if False:`
- `if TYPE_CHECKING:`
