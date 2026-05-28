# Async Mocking Patterns

Detailed patterns for mocking async code in pytest.

## AsyncMock Basics

`AsyncMock` is a mock that returns a coroutine when called. Available in Python 3.8+ via `unittest.mock`.

```python
from unittest.mock import AsyncMock, MagicMock

# AsyncMock returns coroutine
async_mock = AsyncMock(return_value=42)
result = await async_mock()  # Returns 42

# MagicMock does NOT work for async
sync_mock = MagicMock(return_value=42)
result = await sync_mock()  # TypeError!
```

## Mocking with pytest-mock

### Patch Object Method

```python
@pytest.mark.asyncio
async def test_api_client(mocker):
    mocker.patch.object(
        ApiClient,
        "fetch_data",
        AsyncMock(return_value={"status": "ok"})
    )

    client = ApiClient()
    result = await client.fetch_data()
    assert result["status"] == "ok"
```

### Patch Module Function

```python
@pytest.mark.asyncio
async def test_external_call(mocker):
    mocker.patch(
        "myapp.services.external_api.call",
        AsyncMock(return_value={"data": "mocked"})
    )

    result = await process_data()
    assert result["data"] == "mocked"
```

### Patch as Context Manager

```python
@pytest.mark.asyncio
async def test_with_context(mocker):
    with mocker.patch.object(Client, "get", AsyncMock(return_value={})):
        result = await Client().get()
        assert result == {}
```

## Mocking aiohttp

### Mock ClientSession

```python
@pytest.mark.asyncio
async def test_http_get(mocker):
    # Create mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"key": "value"})

    # Create mock context manager for session.get()
    mock_get = AsyncMock()
    mock_get.__aenter__.return_value = mock_response
    mock_get.__aexit__.return_value = None

    # Create mock session
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_get

    # Mock ClientSession context manager
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = None

    mocker.patch("aiohttp.ClientSession", return_value=mock_session_cm)

    # Test code that uses aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get("http://example.com") as resp:
            data = await resp.json()

    assert data == {"key": "value"}
```

### Simplified aiohttp Mock Fixture

```python
@pytest.fixture
def mock_aiohttp_get(mocker):
    def _mock(url_responses: dict):
        """
        url_responses: {url: response_data}
        """
        async def mock_get(url, **kwargs):
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(
                return_value=url_responses.get(url, {})
            )
            return mock_resp

        mock_session = AsyncMock()
        mock_session.get = mock_get

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_session
        mock_cm.__aexit__.return_value = None

        mocker.patch("aiohttp.ClientSession", return_value=mock_cm)

    return _mock

@pytest.mark.asyncio
async def test_with_fixture(mock_aiohttp_get):
    mock_aiohttp_get({
        "http://api.example.com/users": [{"id": 1}],
        "http://api.example.com/posts": [{"id": 1}],
    })

    # Your code using aiohttp...
```

## Mocking Async Database Operations

### Mock asyncpg

```python
@pytest_asyncio.fixture
async def mock_db(mocker):
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ])
    mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "name": "Alice"})
    mock_conn.execute = AsyncMock(return_value="INSERT 1")

    mock_pool = AsyncMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_pool.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.__aexit__ = AsyncMock(return_value=None)

    mocker.patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool))
    return mock_pool

@pytest.mark.asyncio
async def test_database_query(mock_db):
    repo = UserRepository(pool=mock_db)
    users = await repo.get_all()
    assert len(users) == 2
```

### Mock SQLAlchemy AsyncSession

```python
@pytest_asyncio.fixture
async def mock_session(mocker):
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    # Mock query result
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = [
        User(id=1, name="Test")
    ]
    session.execute.return_value = mock_result

    return session
```

## Side Effects

### Multiple Return Values

```python
mock = AsyncMock(side_effect=[
    {"page": 1, "data": [1, 2]},
    {"page": 2, "data": [3, 4]},
    {"page": 3, "data": []},
])

# First call
result1 = await mock()  # {"page": 1, ...}
# Second call
result2 = await mock()  # {"page": 2, ...}
```

### Conditional Returns

```python
def side_effect_fn(url):
    if "users" in url:
        return {"users": []}
    elif "posts" in url:
        return {"posts": []}
    raise ValueError(f"Unknown URL: {url}")

mock = AsyncMock(side_effect=side_effect_fn)
```

### Raising Exceptions

```python
# Always raise
mock = AsyncMock(side_effect=ConnectionError("Network error"))

# Raise then succeed
mock = AsyncMock(side_effect=[
    ConnectionError("First attempt failed"),
    {"status": "ok"},  # Second attempt succeeds
])
```

## Assertion Methods

```python
# Call assertions
mock.assert_called()
mock.assert_called_once()
mock.assert_called_with("expected_arg")
mock.assert_called_once_with("expected_arg", key="value")
mock.assert_not_called()

# Await-specific assertions (AsyncMock only)
mock.assert_awaited()
mock.assert_awaited_once()
mock.assert_awaited_with("expected_arg")
mock.assert_awaited_once_with("expected_arg")
mock.assert_not_awaited()

# Call history
mock.call_count  # Number of calls
mock.call_args  # Last call args
mock.call_args_list  # All call args
mock.await_count  # Number of awaits
mock.await_args  # Last await args
mock.await_args_list  # All await args
```

## Spying on Async Functions

```python
@pytest.mark.asyncio
async def test_spy(mocker):
    # Spy wraps real function but tracks calls
    spy = mocker.patch.object(
        service,
        "process",
        wraps=service.process  # Call real implementation
    )

    result = await service.process(data)

    spy.assert_called_once_with(data)
    assert result == expected  # Real result
```

## Common Mistakes

### Using MagicMock Instead of AsyncMock

```python
# ❌ Wrong - MagicMock doesn't return coroutine
mocker.patch.object(Client, "fetch", MagicMock(return_value={}))

# ✅ Correct - AsyncMock returns awaitable
mocker.patch.object(Client, "fetch", AsyncMock(return_value={}))
```

### Forgetting to Await

```python
# ❌ Wrong - comparing coroutine to expected value
result = mock_async_fn()  # Returns coroutine, not result
assert result == expected  # Always False!

# ✅ Correct
result = await mock_async_fn()
assert result == expected
```

### Wrong Patch Target

```python
# If your code does: from myapp.client import fetch
# ❌ Wrong - patches original location
mocker.patch("external_lib.fetch", AsyncMock())

# ✅ Correct - patches where it's imported
mocker.patch("myapp.client.fetch", AsyncMock())
```
