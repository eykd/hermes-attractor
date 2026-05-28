# Mocking Patterns in Pytest

## When to Mock

### Always Mock
- External HTTP APIs
- Database in unit tests
- File system I/O (or use tmp_path)
- Time-dependent operations
- Random number generation
- Email/SMS services
- Payment gateways

### Never Mock
- Value objects and data structures
- The subject under test
- Code you don't own (wrap it first, mock the wrapper)
- Simple pure functions

## monkeypatch Reference

### Attribute Manipulation
```python
def test_path_home(monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: Path("/mock/home"))
    assert get_user_dir() == Path("/mock/home/.config")

def test_disable_feature(monkeypatch):
    monkeypatch.setattr("myapp.config.FEATURE_ENABLED", False)
    assert not is_feature_available()
```

### Environment Variables
```python
def test_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key-123")
    config = load_config()
    assert config.api_key == "test-key-123"

def test_missing_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ConfigError):
        load_config()
```

### Dictionary Items
```python
def test_settings(monkeypatch):
    monkeypatch.setitem(app.settings, "debug", True)
    assert app.is_debug_mode()
```

### Context Manager Scope
```python
def test_scoped_patch(monkeypatch):
    original = some_module.function

    with monkeypatch.context() as m:
        m.setattr(some_module, "function", mock_fn)
        assert some_module.function() == "mocked"

    assert some_module.function == original
```

## pytest-mock Reference

### Basic Patching
```python
def test_email_sent(mocker):
    mock_send = mocker.patch("myapp.email.send_email")

    notify_user(user_id=1, message="Hello")

    mock_send.assert_called_once()
```

### Patch with Return Value
```python
def test_api_response(mocker):
    mocker.patch(
        "myapp.client.fetch",
        return_value={"status": "ok", "data": [1, 2, 3]}
    )

    result = process_data()
    assert result == [1, 2, 3]
```

### Patch with Side Effect
```python
# Return different values on successive calls
def test_retry_logic(mocker):
    mock_api = mocker.patch("myapp.api.call")
    mock_api.side_effect = [
        ConnectionError("Failed"),
        ConnectionError("Failed again"),
        {"status": "success"}
    ]

    result = call_with_retry()
    assert result["status"] == "success"
    assert mock_api.call_count == 3

# Raise exception
def test_error_handling(mocker):
    mocker.patch(
        "myapp.db.query",
        side_effect=DatabaseError("Connection lost")
    )

    with pytest.raises(ServiceError):
        fetch_users()
```

### Spy (Track Calls Without Replacing)
```python
def test_caching(mocker):
    spy = mocker.spy(expensive_module, "compute")

    result1 = cached_compute(5)
    result2 = cached_compute(5)  # Should use cache

    assert spy.call_count == 1  # Only computed once
```

### Mock with spec
```python
def test_with_spec(mocker):
    # Mock respects interface of real class
    mock_repo = mocker.Mock(spec=UserRepository)

    mock_repo.find_by_id(1)       # OK
    mock_repo.nonexistent()       # Raises AttributeError
```

## Mock Assertion Methods

```python
mock = mocker.Mock()

# Call verification
mock.assert_called()                    # Called at least once
mock.assert_called_once()               # Called exactly once
mock.assert_not_called()                # Never called

# Argument verification
mock.assert_called_with(1, 2, key="val")      # Last call args
mock.assert_called_once_with(1, 2)            # Only call args
mock.assert_any_call(1, 2)                    # Any call matched

# Multiple calls
mock.assert_has_calls([
    call(1),
    call(2),
    call(3)
], any_order=False)

# Accessing call info
mock.call_args        # Last call's args
mock.call_args_list   # All calls' args
mock.call_count       # Number of calls
```

## Pattern: Mock Class Instance

```python
def test_http_client(mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": 1}

    mock_get = mocker.patch("requests.get", return_value=mock_response)

    result = fetch_user(1)

    mock_get.assert_called_with("https://api.example.com/users/1")
    assert result["id"] == 1
```

## Pattern: Mock Context Manager

```python
def test_file_read(mocker):
    mock_open = mocker.mock_open(read_data="file content")
    mocker.patch("builtins.open", mock_open)

    result = read_config_file()

    mock_open.assert_called_with("config.txt", "r")
    assert result == "file content"
```

## Pattern: Mock datetime

```python
from freezegun import freeze_time

@freeze_time("2024-01-15 10:30:00")
def test_timestamp():
    record = create_record()
    assert record.created_at == datetime(2024, 1, 15, 10, 30, 0)

# Or with pytest-freezegun
def test_expiration(freezer):
    sub = create_subscription()

    freezer.move_to("2024-02-15")

    assert sub.is_expired()
```

## Pattern: Mock Async Functions

```python
@pytest.mark.asyncio
async def test_async_fetch(mocker):
    mock_fetch = mocker.patch(
        "myapp.client.async_fetch",
        return_value=AsyncMock(return_value={"data": "value"})
    )

    result = await fetch_data()
    assert result["data"] == "value"
```

## Pattern: Fixture-Based Mocking

```python
@pytest.fixture
def mock_api(mocker):
    """Reusable API mock across tests."""
    mock = mocker.patch("myapp.external.api")
    mock.return_value = {"status": "ok"}
    return mock

def test_success(mock_api):
    result = call_api()
    assert result["status"] == "ok"

def test_failure(mock_api):
    mock_api.side_effect = APIError("timeout")
    with pytest.raises(ServiceError):
        call_api()
```

## Common Mistakes

### Mistake: Wrong Patch Location
```python
# myapp/service.py
from myapp.client import fetch_data

def process():
    return fetch_data()

# WRONG: Patching where defined
mocker.patch("myapp.client.fetch_data")

# CORRECT: Patch where used
mocker.patch("myapp.service.fetch_data")
```

### Mistake: Forgetting Return Value
```python
# WRONG: Mock returns Mock by default
mock_db = mocker.patch("myapp.db.query")
result = get_users()  # Returns Mock, not list

# CORRECT: Set return value
mock_db = mocker.patch("myapp.db.query", return_value=[])
```

### Mistake: Over-mocking
```python
# WRONG: Mocking everything
def test_calc(mocker):
    mock_add = mocker.patch("myapp.math.add")
    mock_mult = mocker.patch("myapp.math.multiply")
    # What are we even testing?

# CORRECT: Use real code
def test_calc():
    assert calculate(2, 3) == 11  # 2 + 3*3
```
