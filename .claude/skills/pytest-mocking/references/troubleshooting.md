# Mocking Troubleshooting Guide

## Common Errors

### "fixture 'mocker' not found"

**Cause**: pytest-mock not installed or not recognized.

**Solution**:
```bash
uv add --group=test pytest-mock
```

Verify installation:
```python
import pytest_mock
print(pytest_mock.__version__)
```

### "AssertionError: Expected call not found"

**Cause**: Mock was called with different arguments than asserted.

**Debug**:
```python
def test_debug_calls(mocker):
    mock = mocker.patch("myapp.send")

    do_something()

    # Print actual calls
    print(f"Called: {mock.called}")
    print(f"Call count: {mock.call_count}")
    print(f"Call args: {mock.call_args}")
    print(f"All calls: {mock.call_args_list}")

    # Then assert
    mock.assert_called_with(expected_arg)
```

### Mock Returns Mock Instead of Expected Value

**Cause**: Forgot to set `return_value`.

```python
# WRONG
mock = mocker.patch("myapp.fetch_data")
result = fetch_data()  # Returns Mock object

# CORRECT
mock = mocker.patch("myapp.fetch_data", return_value={"data": "value"})
result = fetch_data()  # Returns {"data": "value"}
```

### Patch Has No Effect

**Cause**: Patching wrong location.

```python
# myapp/service.py
from myapp.client import fetch  # fetch is imported HERE

def process():
    return fetch()

# WRONG: Patching where defined
mocker.patch("myapp.client.fetch")  # Has no effect on service.py

# CORRECT: Patch where used (where it's imported)
mocker.patch("myapp.service.fetch")
```

**Debug**: Add print to confirm patch target:
```python
def test_patch_location(mocker):
    mock = mocker.patch("myapp.service.fetch")
    print(f"Patched: {myapp.service.fetch}")  # Should show Mock
    print(f"Original: {myapp.client.fetch}")  # Should show real function
```

### "AttributeError: Mock object has no attribute"

**Cause**: Using `spec` and accessing non-existent attribute.

```python
mock = mocker.Mock(spec=RealClass)
mock.real_method()      # OK
mock.fake_method()      # AttributeError

# Solution: Remove spec or add attribute to real class
mock = mocker.Mock()  # No spec, any attribute works
```

### side_effect StopIteration

**Cause**: List of values exhausted.

```python
# WRONG: Only 2 values, called 3 times
mock.side_effect = [1, 2]
mock()  # 1
mock()  # 2
mock()  # StopIteration!

# SOLUTION 1: Provide enough values
mock.side_effect = [1, 2, 3, 3, 3]  # Last value repeated manually

# SOLUTION 2: Use function for infinite values
def always_return_default():
    return "default"
mock.side_effect = always_return_default

# SOLUTION 3: Use cycle
from itertools import cycle
mock.side_effect = cycle([1, 2, 3])
```

### Async Mock Not Awaited

**Cause**: Using regular Mock for async function.

```python
# WRONG
mock = mocker.patch("myapp.async_fetch")
await async_fetch()  # Returns coroutine, not result

# CORRECT
from unittest.mock import AsyncMock
mock = mocker.patch("myapp.async_fetch", new_callable=AsyncMock)
mock.return_value = {"data": "value"}
result = await async_fetch()  # Returns {"data": "value"}
```

### Mock Not Reset Between Tests

**Cause**: Using module-scoped fixture without reset.

```python
# WRONG: Mock accumulates calls across tests
@pytest.fixture(scope="module")
def mock_api(mocker):
    return mocker.patch("myapp.api")

# CORRECT: Function scope (default) or reset manually
@pytest.fixture
def mock_api(mocker):
    mock = mocker.patch("myapp.api")
    yield mock
    # Cleanup automatic with function scope

# OR reset in test
def test_after_reset(mock_api):
    mock_api.reset_mock()
    # Fresh mock
```

## Debugging Techniques

### Print All Mock Interactions

```python
def test_debug_mock(mocker):
    mock = mocker.patch("myapp.external.call")

    run_code_under_test()

    # Comprehensive debug output
    print("=== Mock Debug ===")
    print(f"called: {mock.called}")
    print(f"call_count: {mock.call_count}")
    print(f"call_args: {mock.call_args}")
    print(f"call_args_list: {mock.call_args_list}")
    print(f"return_value: {mock.return_value}")
    print(f"side_effect: {mock.side_effect}")
```

### Verify Patch Target Is Correct

```python
def test_verify_patch(mocker):
    import myapp.service

    print(f"Before patch: {myapp.service.external_call}")

    mock = mocker.patch("myapp.service.external_call")

    print(f"After patch: {myapp.service.external_call}")
    # Should show: <MagicMock ...>
```

### Use assert_called with ANY

```python
from unittest.mock import ANY

def test_partial_match(mocker):
    mock = mocker.patch("myapp.log")

    process(data={"id": 1, "timestamp": datetime.now()})

    # Match id, ignore dynamic timestamp
    mock.assert_called_with(
        event_type="processed",
        data={"id": 1, "timestamp": ANY}
    )
```

### Capture Call Arguments

```python
def test_capture_args(mocker):
    mock = mocker.patch("myapp.send_email")

    process_order(order_id=123)

    # Access captured arguments
    args, kwargs = mock.call_args

    assert kwargs["to"] == "customer@example.com"
    assert "Order 123" in kwargs["subject"]
```

## Design Issues

### Test Is Hard to Write

**Symptom**: Need to mock many things.

**Cause**: Code has too many dependencies.

**Solution**: Refactor production code.
- Extract dependencies to constructor (dependency injection)
- Create wrapper classes for external services
- Split large functions into smaller units

### Test Passes But Production Fails

**Symptom**: Mocked code works, real code doesn't.

**Causes**:
1. Mock doesn't match real behavior
2. Over-mocking hides bugs

**Solutions**:
- Add integration tests with real dependencies
- Use `spec=RealClass` to enforce interface
- Verify mock setup matches real API responses
- Reduce mocking scope

### Tests Break on Refactor

**Symptom**: Changing implementation breaks tests.

**Cause**: Testing implementation, not behavior.

```python
# BRITTLE: Tests internal call sequence
def test_brittle(mocker):
    mock_helper = mocker.patch("myapp.service._internal_helper")
    process_order()
    mock_helper.assert_called_once()

# ROBUST: Tests public behavior
def test_robust():
    result = process_order(order_data)
    assert result.status == "completed"
```

## Fixture Issues

### Fixture Order Matters

```python
# Mock must be created before using it
@pytest.fixture
def setup_data(mock_db):  # mock_db must exist first
    mock_db.return_value = [{"id": 1}]
    return mock_db

@pytest.fixture
def mock_db(mocker):
    return mocker.patch("myapp.database.query")
```

### Autouse Fixture Affects All Tests

```python
# CAREFUL: This mocks for ALL tests in module
@pytest.fixture(autouse=True)
def mock_time(mocker):
    mocker.patch("time.sleep")

# BETTER: Explicit fixture usage
@pytest.fixture
def fast_test(mocker):
    mocker.patch("time.sleep")

def test_needs_mock(fast_test):
    pass  # Mock active

def test_needs_real():
    pass  # No mock
```

### conftest.py Fixture Scope

```python
# conftest.py
# Available to all tests in directory and subdirectories

@pytest.fixture
def mock_api(mocker):  # mocker is function-scoped
    return mocker.patch("myapp.api")

# PROBLEM: Can't use function-scoped mocker in session fixture
# @pytest.fixture(scope="session")
# def global_mock(mocker):  # ERROR: Scope mismatch
#     return mocker.patch("myapp.api")
```

## Performance Issues

### Slow Test Startup

**Cause**: Importing heavy modules during patch.

**Solution**: Patch at module level or use lazy imports.

```python
# If myapp.heavy imports slow modules
mocker.patch("myapp.heavy.slow_function")  # Imports myapp.heavy

# Better: Patch the specific attribute
mocker.patch.object(myapp.heavy, "slow_function")
```

### Memory Leaks

**Cause**: Mocks not cleaned up.

**Solution**: Use mocker fixture (auto-cleanup) instead of manual patching.

```python
# WRONG: Manual patch without cleanup
def test_leaky():
    patcher = patch("myapp.func")
    patcher.start()
    # Forgot patcher.stop()

# CORRECT: mocker handles cleanup
def test_clean(mocker):
    mocker.patch("myapp.func")
    # Automatic cleanup after test
```
