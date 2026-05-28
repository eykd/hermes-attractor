---
name: pytest-async-testing
description: "Use when: (1) Testing async/await functions and coroutines, (2) Creating async fixtures, (3) Mocking async code with AsyncMock, (4) Testing aiohttp clients or async database ops, (5) Debugging event loop errors, (6) Testing Django async views/ORM/Channels."
---

# Async Testing with Pytest

Test async code using pytest-asyncio. Core principle: mock external services, test behavior not implementation.

## Installation

```bash
uv add --group=test pytest pytest-asyncio pytest-mock aiohttp
```

## Basic Async Test

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await async_add(1, 2)
    assert result == 3
```

Key elements:
- `@pytest.mark.asyncio` marks test as async
- `async def` defines coroutine test
- `await` calls async functions

## Async Fixtures

Use `@pytest_asyncio.fixture` for async setup/teardown:

```python
import pytest_asyncio

@pytest_asyncio.fixture
async def database():
    db = await Database.connect()
    yield db
    await db.disconnect()

@pytest.mark.asyncio
async def test_query(database):
    result = await database.query("SELECT 1")
    assert result == 1
```

### Factory Pattern (Async)

```python
@pytest_asyncio.fixture
async def create_user():
    created = []

    async def _create(name="Test"):
        user = await User.create(name=name)
        created.append(user)
        return user

    yield _create
    for user in created:
        await user.delete()
```

### Fixture Scopes

```python
@pytest_asyncio.fixture(scope="module")
async def shared_client():
    client = await AsyncClient.create()
    yield client
    await client.close()
```

## Mocking Async Code

### AsyncMock (Python 3.8+)

```python
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_mocked_api(mocker):
    mock_response = {"status": 200, "data": "test"}
    mocker.patch.object(
        ApiClient, "fetch",
        AsyncMock(return_value=mock_response)
    )

    client = ApiClient()
    result = await client.fetch()

    assert result["status"] == 200
```

### Mock Side Effects

```python
# Multiple return values
mock = AsyncMock(side_effect=[{"page": 1}, {"page": 2}])

# Raise exception
mock = AsyncMock(side_effect=ConnectionError("Network error"))
```

### Mock Assertions

```python
mock.assert_called_once()
mock.assert_called_with(arg1, kwarg=value)
mock.assert_awaited_once()
mock.assert_awaited_with(expected_arg)
```

## Configuration

### pytest.ini

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

### pyproject.toml

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

| Mode | Behavior |
|------|----------|
| `strict` | Requires `@pytest.mark.asyncio` on every async test (default) |
| `auto` | Automatically treats async functions as async tests |

## Common Patterns

### Testing Concurrent Operations

```python
@pytest.mark.asyncio
async def test_concurrent():
    results = await asyncio.gather(
        fetch(1), fetch(2), fetch(3)
    )
    assert len(results) == 3
```

### Testing Timeouts

```python
@pytest.mark.asyncio
async def test_timeout():
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_operation(), timeout=0.1)
```

### Testing Exceptions

```python
@pytest.mark.asyncio
async def test_raises():
    with pytest.raises(ValueError, match="invalid"):
        await validate(-1)
```

### Testing Context Managers

```python
@pytest.mark.asyncio
async def test_async_context():
    async with AsyncConnection() as conn:
        assert conn.connected
    assert not conn.connected
```

## Best Practices

1. **Always mock external services** — Real network calls make tests slow and flaky
2. **One behavior per test** — Clear failure messages
3. **Use appropriate fixture scopes** — Default to `function`, broaden only when needed
4. **Clean up resources** — Use `yield` with try/finally
5. **Test error paths** — Verify exception handling

## Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Real API calls | Slow, flaky | Mock with AsyncMock |
| Missing `await` | RuntimeWarning, wrong results | Always await coroutines |
| Wrong fixture decorator | Fixture not found errors | Use `@pytest_asyncio.fixture` |
| Session-scoped mutable fixtures | Test pollution | Use function scope |

## Quick Decision Guide

**"Which fixture decorator?"**
- Sync fixture? → `@pytest.fixture`
- Async fixture? → `@pytest_asyncio.fixture`

**"Need to mock async function?"**
- Use `AsyncMock(return_value=...)` or `AsyncMock(side_effect=...)`

**"Event loop errors?"**
- Check fixture scopes match
- See [references/troubleshooting.md](references/troubleshooting.md)

## Related Skills

For comprehensive async testing coverage:

- **[django-pytest-patterns](../django-pytest-patterns/SKILL.md)**: Django-specific async view and ORM testing patterns
- **[pytest-fixtures](../pytest-fixtures/SKILL.md)**: Fixture patterns for async fixtures with proper scopes
- **[pytest-mocking](../pytest-mocking/SKILL.md)**: Mocking patterns (use AsyncMock for async code)

## References

- **Mocking patterns**: See [references/mocking.md](references/mocking.md) for aiohttp, database mocking
- **Troubleshooting**: See [references/troubleshooting.md](references/troubleshooting.md) for common errors
- **Real-world examples**: See [references/examples.md](references/examples.md) for complete patterns
- **Django async**: See [references/django.md](references/django.md) for async views, ORM, and Channels (delegates to [django-pytest-patterns](../django-pytest-patterns/SKILL.md) for Django-specific patterns)
