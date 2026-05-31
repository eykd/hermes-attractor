# Test Conventions for hermes-attractor

## Organization

Tests mirror `src/hermes_attractor/` and are split by type, each with a marker:

- **`unit/`** (`@pytest.mark.unit`): fast, isolated, no I/O; mock external deps.
- **`integration/`** (`@pytest.mark.integration`): components together; real I/O in `tmp_path`.
- **`contract/`** (`@pytest.mark.contract`): verify ports/adapters and the plugin
  registration contract (e.g. a fake `PluginContext` that records registrations).

Set the marker once per module: `pytestmark = pytest.mark.unit`.

## Naming

Mirror source structure (`src/hermes_attractor/domain/echo.py` →
`tests/unit/domain/test_echo.py`). Name tests for behavior:
`test_handle_echo_missing_message_returns_error`.

## Strict typing in tests, too

`pyright` (strict) and `ruff` lint `tests/` as well as `src/`. So:

- Every test function is annotated `-> None`; every fixture/param is typed.
- Every public test function and helper class needs a docstring (ruff `D`).
- `reportUnusedCallResult` is an error: when a call's result is intentionally discarded
  (e.g. inside `pytest.raises`), assign it: `_ = EchoMessage(value="")`.
- Type-only imports go under `if TYPE_CHECKING:`.

## Coverage

- **100% required** (`fail_under = 100`), branch coverage on.
- `ports/*` and `_version.py` are coverage-omitted; everything else must be fully covered,
  including both branches of every conditional and the error path of each `tools.py` handler.
- Use `# pragma: no cover` only with a justified reason.

## Patterns

### Exception testing
```python
def test_echo_rejects_empty() -> None:
    """Raise InvalidEchoError for an empty message."""
    with pytest.raises(InvalidEchoError):
        _ = echo("")
```

### Test doubles for ports (structural typing — no inheritance needed)
```python
class _FixedClock:
    """A test double Clock returning a fixed moment."""

    def __init__(self, moment: datetime) -> None:
        """Store the fixed moment."""
        super().__init__()
        self._moment = moment

    def now(self) -> datetime:
        """Return the fixed moment."""
        return self._moment
```

### Parametrize for multiple cases
```python
@pytest.mark.parametrize(("given", "expected"), [("a", "a"), ("b", "b")])
def test_echo_roundtrip(given: str, expected: str) -> None:
    """Echo returns the message unchanged."""
    assert echo(given).value == expected
```

### Mocking
Use `pytest-mock`'s `mocker` fixture or `monkeypatch` for isolation; prefer real
in-process objects and `tmp_path` over mocks where practical.

## Running

```bash
uv run pytest                 # all tests, 100% coverage
uv run pytest tests/unit      # a directory
uv run pytest -m unit         # by marker
uv run pytest -x --lf         # stop on first failure / last failed
just test                     # full gate
just test-quick               # no coverage
just test-hermes              # live hermes-agent integration suite (see below)
```

### Live hermes-agent integration suite

`hermes-agent` (pinned `>=0.15.2`) is in the **`test` dependency-group**, so the hermes-coupled
integration tests (`test_hermes_runtime_contract.py`, `test_reconcile_runtime.py`) **run as part
of the default `uv run pytest`** and contribute to the 100% coverage gate (they cover the
`reconcile_hook` / `attractor-reconcile` CLI / `_runtime_*` seams against the real backend). Run
just the integration subset with:

```bash
just test-hermes   # ≡ uv run pytest tests/integration -v -m integration
```

These are **hermetic and repeatable**: `tests/integration/conftest.py` isolates each test to a
fresh `tmp_path` `HERMES_HOME` + kanban DB (no `hermes setup`, no model key). The
`pytest.importorskip` guards remain as a graceful fallback if the `test` group is ever absent,
but in the normal env the tests run. `conftest.py` fixtures import `hermes_cli` / `tools` lazily
(via `importlib`). The hermes-coupled test files stay in the `[tool.pyright]` `exclude` list:
`hermes-agent` ships no type stubs, so pyright (strict) would flag its untyped surface.

## Applicable skills

`/pytest-unit-tests`, `/pytest-integration-tests`, `/pytest-acceptance-tests`,
`/pytest-fixtures`, `/pytest-parametrize`, `/pytest-mocking`, `/pytest-hypothesis`,
`/pytest-coverage`, `/pytest-test-review`.

## See also

- [CLAUDE.md](../CLAUDE.md) — project-wide conventions.
