# Async Testing Troubleshooting

Common errors and solutions when testing async code with pytest.

## Error: "RuntimeWarning: coroutine was never awaited"

### Cause
Forgetting to `await` an async function.

### Solution
```python
# ❌ Wrong
@pytest.mark.asyncio
async def test_missing_await():
    result = async_function()  # Missing await!
    assert result == expected

# ✅ Correct
@pytest.mark.asyncio
async def test_with_await():
    result = await async_function()
    assert result == expected
```

## Error: "Event loop is closed"

### Cause
Trying to use an event loop that has been closed, often when using session-scoped fixtures with function-scoped tests.

### Solution 1: Match fixture scopes
```python
# If using session-scoped async fixture, ensure event loop matches
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

### Solution 2: Use function scope (recommended)
```python
# Default to function scope for most fixtures
@pytest_asyncio.fixture  # scope="function" is default
async def database():
    db = await connect()
    yield db
    await db.close()
```

## Error: "fixture 'my_async_fixture' not found"

### Cause
Using `@pytest.fixture` instead of `@pytest_asyncio.fixture` for async fixtures.

### Solution
```python
# ❌ Wrong - using pytest.fixture for async
@pytest.fixture
async def my_fixture():
    return await something()

# ✅ Correct - using pytest_asyncio.fixture
import pytest_asyncio

@pytest_asyncio.fixture
async def my_fixture():
    return await something()
```

## Error: "PytestUnraisableExceptionWarning"

### Cause
Async resources not properly cleaned up.

### Solution
```python
@pytest_asyncio.fixture
async def client():
    client = await Client.create()
    try:
        yield client
    finally:
        await client.close()  # Always cleanup
```

## Error: "Task was destroyed but it is pending"

### Cause
Background tasks not awaited before test ends.

### Solution
```python
@pytest.mark.asyncio
async def test_with_background_task():
    task = asyncio.create_task(background_work())

    # Do test work...

    # Always await or cancel background tasks
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
```

## Error: "ScopeMismatch: async fixture has different scope"

### Cause
Async fixture depending on fixture with narrower scope.

### Solution
```python
# ❌ Wrong - session fixture using function fixture
@pytest_asyncio.fixture(scope="session")
async def session_client(function_scoped_db):  # Error!
    ...

# ✅ Correct - match or broaden scope
@pytest_asyncio.fixture(scope="session")
async def session_client(session_scoped_db):
    ...
```

## Error: Test passes but assertions don't run

### Cause
Test function returns coroutine without being awaited (missing marker).

### Solution
```python
# ❌ Wrong - missing marker, test "passes" without running
async def test_without_marker():
    result = await fetch()
    assert result == "expected"

# ✅ Correct - marker ensures test runs as coroutine
@pytest.mark.asyncio
async def test_with_marker():
    result = await fetch()
    assert result == "expected"
```

Or use `asyncio_mode = auto` in pytest config.

## Error: "There is no current event loop"

### Cause
Trying to get event loop outside of async context.

### Solution
```python
# ❌ Wrong
def test_sync_accessing_loop():
    loop = asyncio.get_event_loop()  # May fail
    loop.run_until_complete(async_func())

# ✅ Correct - use async test
@pytest.mark.asyncio
async def test_async():
    result = await async_func()
```

## Error: "RuntimeError: This event loop is already running"

### Cause
Using `asyncio.run()` inside an async test (pytest-asyncio already provides event loop).

### Solution
```python
# ❌ Wrong - nested event loop
@pytest.mark.asyncio
async def test_nested_loop():
    result = asyncio.run(async_func())  # Error!

# ✅ Correct - just await
@pytest.mark.asyncio
async def test_correct():
    result = await async_func()
```

## Mock not being applied

### Cause
Patching wrong location (patch where imported, not where defined).

### Solution
```python
# myapp/service.py
from external_lib import api_call

async def my_service():
    return await api_call()

# ❌ Wrong - patches original location
mocker.patch("external_lib.api_call", AsyncMock())

# ✅ Correct - patches where it's used
mocker.patch("myapp.service.api_call", AsyncMock())
```

## AsyncMock returns coroutine object instead of value

### Cause
Comparing result without awaiting.

### Solution
```python
mock = AsyncMock(return_value=42)

# ❌ Wrong
result = mock()  # Returns coroutine
print(result)  # <coroutine object ...>

# ✅ Correct
result = await mock()  # Returns 42
```

## Tests hang indefinitely

### Cause
1. Deadlock in async code
2. Infinite loop
3. Waiting for event that never fires

### Solution
Use pytest-timeout:

```ini
# pytest.ini
[pytest]
timeout = 10
```

```python
@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_with_timeout():
    await potentially_slow_operation()
```

## Flaky tests with async

### Common causes
1. **Shared state between tests** — Use function-scoped fixtures
2. **Race conditions** — Use proper synchronization
3. **External dependencies** — Mock external services
4. **Time-dependent code** — Use `freezegun` or mock time

### Example fix for time-dependent code
```python
from freezegun import freeze_time

@freeze_time("2024-01-01 12:00:00")
@pytest.mark.asyncio
async def test_time_dependent():
    result = await get_current_timestamp()
    assert result == datetime(2024, 1, 1, 12, 0, 0)
```

## Configuration Quick Reference

### Recommended pytest.ini
```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
filterwarnings =
    error::RuntimeWarning
```

### Event loop fixture (if needed)
```python
# conftest.py
import pytest
import asyncio

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session scope."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
```
