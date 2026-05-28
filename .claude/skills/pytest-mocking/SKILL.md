---
name: pytest-mocking
description: "Use when: (1) Mocking external APIs/databases/services, (2) Using mocker fixture or monkeypatch, (3) Setting up return_value or side_effect, (4) Verifying mock calls, (5) Patching functions/classes/modules, (6) Debugging mock failures, (7) Questions about patch targets."
---

# Effective Mocking in Pytest

## Core Principle

Mock at **boundaries**, not implementations. Replace external systems (APIs, databases, time) while keeping internal logic real. Over-mocking creates tests that pass but miss real bugs.

## When to Mock

| Mock | Don't Mock |
|------|------------|
| External HTTP APIs | Value objects, data structures |
| Database queries (unit tests) | Code under test |
| File system I/O | Pure functions |
| Time (`datetime.now`, `time.sleep`) | Internal helpers |
| Randomness (`random`, `uuid`) | Code you don't own (wrap first) |
| Email/SMS/payment services | Simple transformations |

## Installation

```bash
uv add --group=test pytest-mock
```

## mocker Fixture

The `mocker` fixture from pytest-mock wraps `unittest.mock` with automatic cleanup.

### Basic Patch

```python
def test_sends_notification(mocker):
    mock_send = mocker.patch("myapp.notifications.send_email")

    notify_user(user_id=1)

    mock_send.assert_called_once()
```

### Patch with Return Value

```python
def test_api_response(mocker):
    mocker.patch(
        "myapp.client.fetch_user",
        return_value={"id": 1, "name": "Alice"}
    )

    user = get_user_profile(1)
    assert user["name"] == "Alice"
```

### Patch with side_effect

```python
# Multiple return values
def test_retry_succeeds(mocker):
    mock = mocker.patch("myapp.api.call")
    mock.side_effect = [
        ConnectionError("fail"),
        {"status": "ok"}
    ]

    result = call_with_retry()
    assert result["status"] == "ok"
    assert mock.call_count == 2

# Raise exception
def test_handles_error(mocker):
    mocker.patch("myapp.db.query", side_effect=DatabaseError())

    with pytest.raises(ServiceError):
        fetch_data()

# Dynamic response based on input
def test_dynamic_mock(mocker):
    mock = mocker.patch("myapp.api.get_rate")
    mock.side_effect = lambda currency: {"USD": 1.0, "EUR": 0.85}.get(currency)

    assert get_rate("USD") == 1.0
    assert get_rate("EUR") == 0.85
```

## Mock Assertions

```python
mock = mocker.Mock()

# Call verification
mock.assert_called()                     # At least once
mock.assert_called_once()                # Exactly once
mock.assert_not_called()                 # Never called

# Argument verification
mock.assert_called_with(1, key="val")    # Last call
mock.assert_called_once_with(1, 2)       # Single call with args
mock.assert_any_call(1)                  # Any call matched

# Call sequence
from unittest.mock import call
mock.assert_has_calls([call(1), call(2)])

# Accessing call info
mock.call_count                          # Number of calls
mock.call_args                           # Last call (args, kwargs)
mock.call_args_list                      # All calls
```

## Patch Target Rules

**Patch where imported, not where defined.**

```python
# myapp/service.py
from external_lib import send_request    # Imported HERE

def process():
    return send_request()

# tests/test_service.py
# WRONG: Patch where defined
mocker.patch("external_lib.send_request")

# CORRECT: Patch where used
mocker.patch("myapp.service.send_request")
```

## monkeypatch Fixture

Built-in pytest fixture for simple attribute/env replacement. No mock features (no `assert_called`).

### Environment Variables

```python
def test_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    assert load_config().api_key == "test-key"

def test_missing_var(monkeypatch):
    monkeypatch.delenv("SECRET", raising=False)
```

### Attributes

```python
def test_home_path(monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: Path("/mock"))
    assert get_config_dir() == Path("/mock/.config")

def test_disable_feature(monkeypatch):
    monkeypatch.setattr("myapp.config.FEATURE_FLAG", False)
```

### Dictionary Items

```python
def test_settings(monkeypatch):
    monkeypatch.setitem(app.settings, "timeout", 60)
```

## mocker vs monkeypatch

| Feature | mocker | monkeypatch |
|---------|--------|-------------|
| Source | pytest-mock plugin | Built-in pytest |
| Mock assertions | Yes | No |
| return_value/side_effect | Yes | No |
| Best for | Complex mocks | Simple replacements |
| Use case | APIs, classes | Env vars, constants |

## Common Patterns

### Mock HTTP Response

```python
def test_fetch_user(mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": 1, "name": "Alice"}

    mocker.patch("requests.get", return_value=mock_response)

    user = fetch_user(1)
    assert user["name"] == "Alice"
```

### Mock Class/Method

```python
def test_with_mock_class(mocker):
    MockDB = mocker.patch("myapp.service.Database")
    mock_instance = MockDB.return_value
    mock_instance.query.return_value = [{"id": 1}]

    result = get_users()
    mock_instance.query.assert_called_once()
```

### Spy (Track Without Replacing)

```python
def test_caching(mocker):
    spy = mocker.spy(expensive_module, "compute")

    result1 = cached_compute(5)
    result2 = cached_compute(5)

    assert spy.call_count == 1  # Cached after first call
```

### Mock with spec

```python
def test_type_safe_mock(mocker):
    mock = mocker.Mock(spec=UserRepository)
    mock.find_by_id(1)        # OK
    # mock.invalid_method()   # Raises AttributeError
```

### Fixture-Based Mock

```python
@pytest.fixture
def mock_api(mocker):
    mock = mocker.patch("myapp.external.api_call")
    mock.return_value = {"status": "ok"}
    return mock

def test_success(mock_api):
    assert process()["status"] == "ok"

def test_failure(mock_api):
    mock_api.side_effect = APIError()
    with pytest.raises(ServiceError):
        process()
```

## Common Mistakes

| Mistake | Problem | Solution |
|---------|---------|----------|
| Wrong patch target | Patch where defined, not used | Patch at import location |
| No return_value | Mock returns Mock, not expected data | Set explicit return_value |
| Over-mocking | Tests pass but prod fails | Mock only boundaries |
| Testing implementation | Brittle tests break on refactor | Test behavior via public API |
| Mocking what you test | No actual code runs | Mock dependencies, not subject |

## Quick Reference

```python
# Create mock
mock = mocker.Mock()
mock = mocker.MagicMock()  # With dunder methods
mock = mocker.Mock(spec=RealClass)  # Type-safe

# Patch
mocker.patch("module.function")
mocker.patch.object(Class, "method")
mocker.patch.dict(dict_obj, {"key": "val"})

# Configure
mock.return_value = "value"
mock.side_effect = [1, 2, 3]
mock.side_effect = Exception("error")
mock.side_effect = lambda x: x * 2

# Verify
mock.assert_called_once_with(expected_arg)
assert mock.call_count == 3
```

## Detailed References

- **[advanced-patterns.md](references/advanced-patterns.md)**: Async mocking, datetime/time, context managers, PropertyMock
- **[troubleshooting.md](references/troubleshooting.md)**: Common errors, debugging mocks, fixture issues
