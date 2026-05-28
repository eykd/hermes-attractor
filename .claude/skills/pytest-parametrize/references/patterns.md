# Advanced Parametrization Patterns

Comprehensive patterns for complex parametrization scenarios.

## Combining Parametrize with Marks

### Skip Specific Cases

```python
@pytest.mark.parametrize("browser,version", [
    ("chrome", 120),
    ("firefox", 121),
    pytest.param("safari", 17, marks=pytest.mark.skip(reason="Safari flaky on CI")),
    ("edge", 120),
])
def test_browser_compatibility(browser, version):
    assert is_compatible(browser, version)
```

### XFail for Known Issues

```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (5, 6),
    pytest.param(999, 1000, marks=pytest.mark.xfail(reason="Bug #1234: overflow")),
])
def test_increment(input, expected):
    assert increment(input) == expected
```

### Combining Multiple Marks

```python
@pytest.mark.parametrize("config,expected", [
    pytest.param(
        {"mode": "fast"},
        True,
        marks=[pytest.mark.unit, pytest.mark.smoke],
        id="fast-mode"
    ),
    pytest.param(
        {"mode": "slow"},
        True,
        marks=[pytest.mark.integration, pytest.mark.slow],
        id="slow-mode"
    ),
])
def test_configuration_modes(config, expected):
    assert validate_config(config) == expected
```

## Nested Data Structures

### Parametrizing with Dictionaries

```python
USER_SCENARIOS = [
    pytest.param(
        {
            "username": "admin",
            "roles": ["admin", "user"],
            "permissions": ["read", "write", "delete"],
        },
        True,
        id="admin-full-access"
    ),
    pytest.param(
        {
            "username": "guest",
            "roles": ["guest"],
            "permissions": ["read"],
        },
        False,
        id="guest-limited"
    ),
]

@pytest.mark.parametrize("user_data,can_delete", USER_SCENARIOS)
def test_user_permissions(user_data, can_delete):
    user = User(**user_data)
    assert user.can_delete() == can_delete
```

### Parametrizing with Objects

```python
from dataclasses import dataclass

@dataclass
class TestCase:
    input: str
    expected_output: str
    expected_status: str

    def __str__(self):
        return f"{self.input}->{self.expected_status}"

PARSING_CASES = [
    TestCase(
        input='{"valid": "json"}',
        expected_output={"valid": "json"},
        expected_status="success",
    ),
    TestCase(
        input='invalid json',
        expected_output=None,
        expected_status="error",
    ),
]

@pytest.mark.parametrize("case", PARSING_CASES, ids=str)
def test_json_parsing(case):
    result = parse_json(case.input)
    if case.expected_status == "success":
        assert result == case.expected_output
    else:
        assert result is None
```

## Fixture-Parametrize Combinations

### Parametrize with Multiple Fixtures

```python
@pytest.fixture
def database(request):
    db_type = request.param
    db = create_database(db_type)
    yield db
    db.cleanup()

@pytest.fixture
def cache(request):
    cache_type = request.param
    c = create_cache(cache_type)
    yield c
    c.clear()

@pytest.mark.parametrize("database", ["sqlite", "postgres"], indirect=True)
@pytest.mark.parametrize("cache", ["redis", "memcached"], indirect=True)
def test_caching_with_database(database, cache):
    # Runs 4 times: 2 databases × 2 caches
    result = fetch_with_cache(database, cache, key="test")
    assert result is not None
```

### Parametrize Some Arguments, Fixture Others

```python
@pytest.fixture
def authenticated_client(request):
    user_role = request.param
    client = Client()
    client.login(role=user_role)
    return client

@pytest.mark.parametrize("authenticated_client,endpoint,expected_status", [
    ("admin", "/api/users", 200),
    ("admin", "/api/admin", 200),
    ("user", "/api/users", 200),
    ("user", "/api/admin", 403),
], indirect=["authenticated_client"])
def test_api_access(authenticated_client, endpoint, expected_status):
    response = authenticated_client.get(endpoint)
    assert response.status_code == expected_status
```

## Dynamic Parametrization

### Loading Test Data from Files

```python
import json
from pathlib import Path

def load_test_cases(filename):
    path = Path(__file__).parent / "testdata" / filename
    with path.open() as f:
        data = json.load(f)
    return [
        pytest.param(case["input"], case["expected"], id=case.get("id"))
        for case in data
    ]

@pytest.mark.parametrize("input,expected", load_test_cases("calculations.json"))
def test_calculation_from_file(input, expected):
    assert calculate(input) == expected
```

Example `testdata/calculations.json`:
```json
[
    {"id": "simple-add", "input": {"op": "add", "a": 2, "b": 3}, "expected": 5},
    {"id": "multiply", "input": {"op": "mul", "a": 4, "b": 5}, "expected": 20}
]
```

### Parametrize from Environment

```python
import os

def get_browser_configs():
    browsers = os.getenv("TEST_BROWSERS", "chrome,firefox").split(",")
    return [pytest.param(b, id=b) for b in browsers]

@pytest.mark.parametrize("browser", get_browser_configs())
def test_cross_browser(browser):
    driver = WebDriver(browser)
    assert driver.is_ready()
```

### Conditional Parametrization

```python
import sys

PYTHON_VERSION_CASES = [
    pytest.param("feature_a", marks=pytest.mark.skipif(
        sys.version_info < (3, 10),
        reason="Requires Python 3.10+"
    )),
    pytest.param("feature_b"),
]

@pytest.mark.parametrize("feature", PYTHON_VERSION_CASES)
def test_python_version_features(feature):
    assert has_feature(feature)
```

## ID Generation Strategies

### Complex ID Functions

```python
def make_id(val):
    """Generate descriptive IDs for complex test cases."""
    if isinstance(val, dict):
        parts = [f"{k}={v}" for k, v in val.items()]
        return "-".join(parts)
    elif isinstance(val, list):
        return f"list[{len(val)}]"
    elif val is None:
        return "none"
    else:
        return str(val)[:20]  # Truncate long strings

@pytest.mark.parametrize("config", [
    {"timeout": 30, "retries": 3},
    {"timeout": 60, "retries": 1},
    None,
], ids=make_id)
def test_client_config(config):
    client = Client(config)
    assert client.is_configured()
```

**Output:**
```
test_client_config[timeout=30-retries=3] PASSED
test_client_config[timeout=60-retries=1] PASSED
test_client_config[none] PASSED
```

### IDs from Attributes

```python
class Scenario:
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __str__(self):
        return self.name

SCENARIOS = [
    Scenario("low-load", 10),
    Scenario("medium-load", 100),
    Scenario("high-load", 1000),
]

@pytest.mark.parametrize("scenario", SCENARIOS, ids=str)
def test_performance(scenario):
    result = process(scenario.value)
    assert result.is_successful()
```

## Parametrize with Hypothesis Integration

Combine parametrize for structure with Hypothesis for data:

```python
from hypothesis import given, strategies as st

@pytest.mark.parametrize("operation", ["add", "multiply", "subtract"])
@given(a=st.integers(), b=st.integers())
def test_commutative_operations(operation, a, b):
    if operation in ["add", "multiply"]:
        assert calc(operation, a, b) == calc(operation, b, a)
```

For more on property-based testing, see **[pytest-hypothesis](../../pytest-hypothesis/SKILL.md)**.

## Scope-Based Parametrization

### Module-Level Parametrized Fixtures

```python
@pytest.fixture(scope="module", params=["dev", "staging", "prod"])
def environment(request):
    """Shared environment configuration across module tests."""
    env = request.param
    config = load_config(env)
    setup_environment(config)
    yield config
    teardown_environment(config)

def test_feature_a(environment):
    # Runs 3 times with different environments
    assert environment["database_url"] is not None

def test_feature_b(environment):
    # Uses same environment instance as test_feature_a (per module)
    assert environment["api_key"] is not None
```

### Session-Level Parametrization

```python
@pytest.fixture(scope="session", params=["v1", "v2"])
def api_version(request):
    """Test against multiple API versions in same session."""
    return request.param

def test_endpoint_compatibility(api_version):
    response = call_api(version=api_version, endpoint="/users")
    assert response.status_code == 200
```

## Error Handling in Parametrized Tests

### Grouping Expected Errors

```python
@pytest.mark.parametrize("input,error_type,error_msg", [
    pytest.param(None, TypeError, "cannot be None", id="none-input"),
    pytest.param(-1, ValueError, "must be positive", id="negative"),
    pytest.param("abc", TypeError, "must be numeric", id="string"),
    pytest.param(0, ValueError, "must be positive", id="zero"),
])
def test_validation_errors(input, error_type, error_msg):
    with pytest.raises(error_type, match=error_msg):
        validate(input)
```

### Mixed Success and Failure Cases

```python
@pytest.mark.parametrize("input,should_raise,expected", [
    pytest.param(10, False, 100, id="valid-positive"),
    pytest.param(0, True, ValueError, id="zero-raises"),
    pytest.param(-5, True, ValueError, id="negative-raises"),
    pytest.param(5, False, 25, id="valid-small"),
])
def test_calculation_with_validation(input, should_raise, expected):
    if should_raise:
        with pytest.raises(expected):
            calculate(input)
    else:
        assert calculate(input) == expected
```

## Debugging Parametrized Tests

### Running Single Case

```bash
# Run only specific parametrized case by ID
pytest test_file.py::test_function[case-id]

# Example:
pytest test_calc.py::test_operations[add-2-3-5]
```

### Using --collect-only to View Cases

```bash
# See all generated test cases without running
pytest --collect-only test_file.py

# Filter by keyword
pytest --collect-only -k "admin"
```

### Verbose Output for Debugging

```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (5, 6),
])
def test_increment(input, expected):
    result = increment(input)
    print(f"DEBUG: input={input}, result={result}, expected={expected}")
    assert result == expected
```

Run with:
```bash
pytest -v -s  # -v for verbose, -s to show prints
```

## Anti-Patterns to Avoid

### Too Many Parameters

```python
# ❌ BAD: Hard to read, hard to maintain
@pytest.mark.parametrize("a,b,c,d,e,f,g,h,expected", [
    (1, 2, 3, 4, 5, 6, 7, 8, 36),
    (2, 3, 4, 5, 6, 7, 8, 9, 44),
])
def test_complex_calculation(a, b, c, d, e, f, g, h, expected):
    assert complex_calc(a, b, c, d, e, f, g, h) == expected

# ✅ GOOD: Use a data structure
@pytest.mark.parametrize("inputs,expected", [
    ([1, 2, 3, 4, 5, 6, 7, 8], 36),
    ([2, 3, 4, 5, 6, 7, 8, 9], 44),
])
def test_complex_calculation(inputs, expected):
    assert complex_calc(*inputs) == expected
```

### Mixing Unrelated Cases

```python
# ❌ BAD: Different behaviors in one test
@pytest.mark.parametrize("input,expected", [
    ("valid@email.com", True),     # Testing email validation
    ("invalid", False),
    (42, TypeError),                # Testing type checking (different behavior!)
])
def test_email_validation(input, expected):
    # Test becomes confusing - needs if/else logic
    ...

# ✅ GOOD: Separate tests for separate behaviors
@pytest.mark.parametrize("email,is_valid", [
    ("valid@email.com", True),
    ("invalid", False),
])
def test_email_validation(email, is_valid):
    assert validate_email(email) == is_valid

@pytest.mark.parametrize("invalid_type", [42, None, [], {}])
def test_email_validation_type_error(invalid_type):
    with pytest.raises(TypeError):
        validate_email(invalid_type)
```

### Over-Parametrization

```python
# ❌ BAD: Parametrizing when not needed
@pytest.mark.parametrize("value", [42])  # Only one case!
def test_single_case(value):
    assert calculate(value) == 1764

# ✅ GOOD: Just write a regular test
def test_single_case():
    assert calculate(42) == 1764
```

### Missing Test IDs

```python
# ❌ BAD: Auto-generated IDs are unreadable
@pytest.mark.parametrize("user", [
    {"name": "Alice", "role": "admin"},
    {"name": "Bob", "role": "user"},
])
def test_permissions(user):
    ...
# Output: test_permissions[user0] test_permissions[user1]

# ✅ GOOD: Use descriptive IDs
@pytest.mark.parametrize("user", [
    pytest.param({"name": "Alice", "role": "admin"}, id="admin-alice"),
    pytest.param({"name": "Bob", "role": "user"}, id="user-bob"),
])
def test_permissions(user):
    ...
# Output: test_permissions[admin-alice] test_permissions[user-bob]
```

## Best Practices Summary

1. **Use descriptive IDs**: Make test output readable
2. **Keep parameters focused**: 2-4 parameters max; use data structures for more
3. **Group related cases**: Constants for test data sets
4. **One behavior per test**: Don't mix different assertions in parametrized tests
5. **Use indirect for complex setup**: Keep test data simple, move complexity to fixtures
6. **Consider Hypothesis for exhaustive testing**: When parameter space is large
7. **Document edge cases**: Use comments or IDs to explain why specific values are tested
