# Advanced Mocking Patterns

## Async Functions

```python
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_async_api(mocker):
    mock_fetch = mocker.patch(
        "myapp.client.async_fetch",
        new_callable=AsyncMock,
        return_value={"data": "value"}
    )

    result = await fetch_data()

    assert result["data"] == "value"
    mock_fetch.assert_awaited_once()

# Async side_effect
@pytest.mark.asyncio
async def test_async_retry(mocker):
    mock = mocker.patch("myapp.api.async_call", new_callable=AsyncMock)
    mock.side_effect = [
        ConnectionError("fail"),
        {"status": "ok"}
    ]

    result = await call_with_retry()
    assert mock.await_count == 2
```

## Mocking datetime/time

### Using freezegun

```python
from freezegun import freeze_time

@freeze_time("2024-06-15 10:30:00")
def test_created_timestamp():
    record = create_record()
    assert record.created_at == datetime(2024, 6, 15, 10, 30, 0)

@freeze_time("2024-01-01")
def test_subscription_expiry():
    sub = Subscription(days=30)

    with freeze_time("2024-02-01"):
        assert sub.is_expired()
```

### Using pytest-freezegun

```python
def test_time_travel(freezer):
    sub = create_subscription(days=7)
    assert not sub.is_expired()

    freezer.move_to("2024-02-01")
    assert sub.is_expired()
```

### Manual datetime mock

```python
def test_current_time(mocker):
    fixed_time = datetime(2024, 6, 15, 12, 0, 0)
    mock_now = mocker.patch("myapp.utils.datetime")
    mock_now.now.return_value = fixed_time
    mock_now.side_effect = lambda *a, **kw: datetime(*a, **kw)

    result = get_timestamp()
    assert result == fixed_time
```

### Mocking time.sleep

```python
def test_no_wait(mocker):
    mock_sleep = mocker.patch("time.sleep")

    slow_function()  # Has time.sleep(60) inside

    mock_sleep.assert_called_with(60)
    # Test completes instantly
```

## Context Managers

### mock_open for files

```python
def test_read_config(mocker):
    mock_file = mocker.mock_open(read_data="key=value\nother=123")
    mocker.patch("builtins.open", mock_file)

    config = read_config("config.txt")

    mock_file.assert_called_with("config.txt", "r")
    assert config["key"] == "value"

def test_write_file(mocker):
    mock_file = mocker.mock_open()
    mocker.patch("builtins.open", mock_file)

    write_data("output.txt", "content")

    mock_file().write.assert_called_with("content")
```

### Custom context manager

```python
def test_database_transaction(mocker):
    mock_conn = mocker.MagicMock()
    mock_conn.__enter__ = mocker.Mock(return_value=mock_conn)
    mock_conn.__exit__ = mocker.Mock(return_value=False)
    mock_conn.execute.return_value = [{"id": 1}]

    mocker.patch("myapp.db.get_connection", return_value=mock_conn)

    result = query_users()
    assert result == [{"id": 1}]
```

## PropertyMock

```python
def test_property(mocker):
    mock_prop = mocker.PropertyMock(return_value="mocked_value")
    mocker.patch.object(MyClass, "my_property", new_callable=mocker.PropertyMock, return_value="test")

    obj = MyClass()
    assert obj.my_property == "test"

# Property with side_effect
def test_property_changes(mocker):
    values = iter(["first", "second", "third"])
    mock_prop = mocker.PropertyMock(side_effect=lambda: next(values))
    mocker.patch.object(MyClass, "status", new=mock_prop)

    obj = MyClass()
    assert obj.status == "first"
    assert obj.status == "second"
```

## Patching Dictionaries

```python
def test_env_vars(mocker):
    mocker.patch.dict("os.environ", {"API_URL": "http://test.local"})

    assert os.environ["API_URL"] == "http://test.local"
    # Original restored after test

def test_clear_and_set(mocker):
    mocker.patch.dict("os.environ", {"ONLY_THIS": "value"}, clear=True)

    assert os.environ == {"ONLY_THIS": "value"}
```

## Multiple Patches

### Using multiple decorators

```python
def test_multiple_patches(mocker):
    mock_api = mocker.patch("myapp.external.api_call")
    mock_db = mocker.patch("myapp.db.query")
    mock_cache = mocker.patch("myapp.cache.get")

    mock_api.return_value = {"data": "from_api"}
    mock_db.return_value = []
    mock_cache.return_value = None

    result = process_request()

    mock_cache.assert_called_once()
    mock_api.assert_called_once()
```

### Nested context managers

```python
def test_nested_patches(mocker):
    with mocker.patch("module.func1") as m1:
        with mocker.patch("module.func2") as m2:
            m1.return_value = "one"
            m2.return_value = "two"
            # Both active here
```

## Partial Mocking

### Mock one method, keep others real

```python
def test_partial_mock(mocker):
    mocker.patch.object(
        UserService,
        "send_notification",
        return_value=True
    )

    service = UserService()
    # send_notification is mocked
    # All other methods are real
    result = service.create_user(data)  # Real method
```

## Autospec

Create mocks that respect the original signature:

```python
def test_with_autospec(mocker):
    mock_service = mocker.patch(
        "myapp.services.EmailService",
        autospec=True
    )

    instance = mock_service.return_value
    instance.send.return_value = True

    # Wrong signature raises TypeError
    # instance.send("wrong", "args", "here")  # Error!
```

## Call Order Verification

```python
from unittest.mock import call

def test_call_sequence(mocker):
    mock_logger = mocker.patch("myapp.logger")

    process_order(order_id=123)

    expected_calls = [
        call.info("Starting order 123"),
        call.debug("Validating..."),
        call.info("Order 123 complete")
    ]
    mock_logger.assert_has_calls(expected_calls, any_order=False)
```

## Reset Mock Between Uses

```python
def test_reset_mock(mocker):
    mock = mocker.Mock()
    mock(1)
    mock(2)

    assert mock.call_count == 2

    mock.reset_mock()

    assert mock.call_count == 0
    mock.assert_not_called()
```

## Wrapping Real Functions

```python
def test_wrap_real_function(mocker):
    real_func = mymodule.expensive_calculation

    mock = mocker.patch(
        "mymodule.expensive_calculation",
        wraps=real_func
    )

    result = mymodule.expensive_calculation(5)

    # Real function executed
    assert result == real_func(5)
    # But we can verify calls
    mock.assert_called_once_with(5)
```

## MagicMock vs Mock

```python
# Mock: Basic mock, attributes created on access
mock = mocker.Mock()
mock.method()  # Works
len(mock)      # TypeError

# MagicMock: Includes dunder methods
magic = mocker.MagicMock()
magic.method()         # Works
len(magic)             # Works, returns 0
magic[0]               # Works
str(magic)             # Works
```

## Sentinel Objects

```python
from unittest.mock import sentinel

def test_with_sentinel(mocker):
    mock = mocker.patch("myapp.generate_token")
    mock.return_value = sentinel.unique_token

    result = create_session()

    assert result.token is sentinel.unique_token
```
