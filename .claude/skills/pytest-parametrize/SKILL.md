---
name: pytest-parametrize
description: "Use when: (1) Testing same logic with multiple input/output pairs, (2) Reducing test duplication, (3) Creating comprehensive edge case coverage, (4) Generating readable test names with custom IDs, (5) Combining parametrize with fixtures (indirect)."
---

# Effective Parametrization with Pytest

## Core Philosophy

Parametrization eliminates test duplication when testing the same behavior with different inputs. Instead of writing N similar tests, write one parametrized test that runs N times with different data.

**When to parametrize:**
- Same assertion logic, different input values
- Testing boundary conditions (min, max, zero, negative, edge cases)
- Verifying multiple examples of a behavior
- Reducing cognitive load by showing patterns rather than repetition

**When NOT to parametrize:**
- Testing different behaviors (use separate tests)
- Setup/teardown differs significantly between cases
- Assertions are fundamentally different
- It makes the test harder to understand

## Quick Start

### Basic Parametrization

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    (5, 25),
    (0, 0),
    (-3, 9),
    (10, 100),
])
def test_square_function(input, expected):
    assert square(input) == expected
```

**Output:**
```
test_square_function[5-25] PASSED
test_square_function[0-0] PASSED
test_square_function[-3-9] PASSED
test_square_function[10-100] PASSED
```

## Core Patterns

### Single Parameter

```python
@pytest.mark.parametrize("value", [1, 2, 3, 5, 8, 13])
def test_fibonacci_values_are_positive(value):
    assert value > 0
```

### Multiple Parameters

```python
@pytest.mark.parametrize("operation,a,b,expected", [
    ("add", 2, 3, 5),
    ("subtract", 10, 4, 6),
    ("multiply", 3, 7, 21),
    ("divide", 20, 4, 5),
])
def test_calculator(operation, a, b, expected):
    calculator = Calculator()
    result = calculator.execute(operation, a, b)
    assert result == expected
```

### Using pytest.param for Custom IDs

Make test output readable with custom test IDs:

```python
@pytest.mark.parametrize("user_type,can_delete", [
    pytest.param("admin", True, id="admin-can-delete"),
    pytest.param("editor", False, id="editor-cannot-delete"),
    pytest.param("viewer", False, id="viewer-cannot-delete"),
])
def test_delete_permissions(user_type, can_delete):
    user = User(type=user_type)
    assert user.has_permission("delete") == can_delete
```

**Output:**
```
test_delete_permissions[admin-can-delete] PASSED
test_delete_permissions[editor-cannot-delete] PASSED
test_delete_permissions[viewer-cannot-delete] PASSED
```

### ID Function for Dynamic Names

```python
def describe_case(val):
    """Generate readable test ID from test case."""
    if isinstance(val, dict):
        return f"{val['email']}-{val['valid']}"
    return str(val)

@pytest.mark.parametrize("email_data", [
    {"email": "user@example.com", "valid": True},
    {"email": "invalid-email", "valid": False},
    {"email": "@missing-local.com", "valid": False},
], ids=describe_case)
def test_email_validation(email_data):
    assert validate_email(email_data["email"]) == email_data["valid"]
```

## Indirect Parametrization

Use `indirect=True` to pass parameters through fixtures for complex setup:

```python
@pytest.fixture
def database(request):
    """Fixture receives parameter via request.param."""
    db_type = request.param
    if db_type == "sqlite":
        db = SQLiteDatabase(":memory:")
    elif db_type == "postgres":
        db = PostgresDatabase("test_db")

    db.connect()
    yield db
    db.disconnect()

@pytest.mark.parametrize("database", ["sqlite", "postgres"], indirect=True)
def test_query_execution(database):
    result = database.execute("SELECT 1")
    assert result is not None
```

**Why use indirect?**
- Complex setup logic belongs in fixtures
- Reuse fixture across multiple test files
- Separate data (test parameters) from infrastructure (fixture setup)

### Partial Indirect

Mix direct and indirect parameters:

```python
@pytest.fixture
def user(request):
    role = request.param
    return User.create(role=role)

@pytest.mark.parametrize("user,action,allowed", [
    ("admin", "delete", True),
    ("editor", "delete", False),
    ("viewer", "delete", False),
], indirect=["user"])  # Only 'user' goes through fixture
def test_permissions(user, action, allowed):
    assert user.can_perform(action) == allowed
```

## Combining Multiple Parametrize Decorators

Stack decorators for cross-product testing:

```python
@pytest.mark.parametrize("browser", ["chrome", "firefox", "safari"])
@pytest.mark.parametrize("viewport", ["mobile", "tablet", "desktop"])
def test_responsive_layout(browser, viewport):
    # Runs 9 times: 3 browsers × 3 viewports
    page = render_page(browser, viewport)
    assert page.is_responsive()
```

**Total tests:** 3 × 3 = 9 test cases

## Parametrizing Fixtures

Make fixtures themselves parametrized:

```python
@pytest.fixture(params=["json", "xml", "yaml"])
def serializer(request):
    format_type = request.param
    return create_serializer(format_type)

def test_serialization_round_trip(serializer):
    # Runs 3 times, once per serializer type
    data = {"key": "value"}
    serialized = serializer.dumps(data)
    deserialized = serializer.loads(serialized)
    assert deserialized == data
```

For more advanced fixture parameterization patterns, see **[pytest-fixtures](../pytest-fixtures/SKILL.md)**.

## Exception Testing with Parametrize

```python
@pytest.mark.parametrize("value,exception,message", [
    (-1, ValueError, "must be positive"),
    (0, ValueError, "must be positive"),
    ("invalid", TypeError, "must be an integer"),
    (None, TypeError, "must be an integer"),
])
def test_input_validation(value, exception, message):
    with pytest.raises(exception, match=message):
        process_value(value)
```

## Readable Test Organization

### Grouping Related Cases

```python
# Group boundary conditions together
BOUNDARY_CASES = [
    pytest.param(0, 0, id="zero"),
    pytest.param(1, 1, id="one"),
    pytest.param(-1, 1, id="negative-one"),
]

LARGE_NUMBERS = [
    pytest.param(1000, 1000000, id="thousand"),
    pytest.param(10000, 100000000, id="ten-thousand"),
]

@pytest.mark.parametrize("input,expected", BOUNDARY_CASES + LARGE_NUMBERS)
def test_square_comprehensive(input, expected):
    assert square(input) == expected
```

### Using Classes for Organization

```python
class TestUserPermissions:
    @pytest.mark.parametrize("role,can_edit", [
        ("admin", True),
        ("editor", True),
        ("viewer", False),
    ])
    def test_edit_permission(self, role, can_edit):
        user = User(role=role)
        assert user.can_edit() == can_edit

    @pytest.mark.parametrize("role,can_delete", [
        ("admin", True),
        ("editor", False),
        ("viewer", False),
    ])
    def test_delete_permission(self, role, can_delete):
        user = User(role=role)
        assert user.can_delete() == can_delete
```

## Common Patterns

### Testing Edge Cases

```python
@pytest.mark.parametrize("text,expected", [
    ("", 0),                    # empty string
    ("a", 1),                   # single char
    ("hello", 5),               # normal case
    ("  spaces  ", 10),         # with spaces
    ("unicode: 你好", 11),       # unicode characters
    ("x" * 1000, 1000),         # long string
])
def test_string_length(text, expected):
    assert len(text) == expected
```

### Date/Time Testing

```python
from datetime import date

@pytest.mark.parametrize("date_input,is_weekend", [
    (date(2024, 1, 1), False),   # Monday
    (date(2024, 1, 6), True),    # Saturday
    (date(2024, 1, 7), True),    # Sunday
    (date(2024, 1, 8), False),   # Monday
])
def test_weekend_detection(date_input, is_weekend):
    assert is_weekend_day(date_input) == is_weekend
```

### HTTP Status Code Testing

```python
@pytest.mark.parametrize("endpoint,method,status", [
    ("/api/users", "GET", 200),
    ("/api/users", "POST", 201),
    ("/api/users/1", "GET", 200),
    ("/api/users/999", "GET", 404),
    ("/api/users/1", "DELETE", 204),
])
def test_api_status_codes(client, endpoint, method, status):
    response = client.request(method, endpoint)
    assert response.status_code == status
```

## When to Use This Skill

**Choose pytest-parametrize when:**
- Testing the same logic with multiple input/output combinations
- Eliminating duplication in similar test cases
- Creating comprehensive test coverage for edge cases
- Testing boundary conditions (empty, single, many, max values)
- Generating readable test reports with custom IDs

**Use a different skill when:**
- Need complex fixture setup → **pytest-fixtures** with fixture params
- Testing fundamentally different behaviors → Separate unit tests
- Need property-based testing with random data → **pytest-hypothesis**
- Testing async functions → **pytest-async-testing** (can combine with parametrize)

## Quick Decision Guide

**"Should I parametrize this?"**
- ✅ Same assertion, different input data
- ✅ Testing boundary values (0, 1, -1, max, min)
- ✅ Covering multiple examples of a rule
- ✅ Reducing copy-paste test code
- ❌ Different test behaviors → Use separate tests
- ❌ Complex, unrelated setups → Use separate tests

**"Direct or indirect parametrization?"**
- Direct: Simple values that don't need setup (strings, numbers, bools)
- Indirect: Complex objects, database connections, expensive setup
- Partial indirect: Mix both for flexibility

**"How to make test IDs readable?"**
- Use `pytest.param(..., id="descriptive-name")`
- Use `ids=` parameter with a function
- Keep IDs short but descriptive (avoid auto-generated `[0]`, `[1]`)

## Related Skills

- **[pytest-fixtures](../pytest-fixtures/SKILL.md)**: Parametrized fixtures and indirect parametrization patterns
- **[pytest-unit-tests](../pytest-unit-tests/SKILL.md)**: Core unit testing with parametrized examples
- **[pytest-hypothesis](../pytest-hypothesis/SKILL.md)**: Property-based testing as alternative to manual parametrization

## References

For advanced parametrization patterns:

- **[patterns.md](references/patterns.md)**: Advanced parametrization techniques and real-world examples
