# Test Anti-Patterns Reference

Comprehensive catalog of test anti-patterns to flag during code review.

## Critical Anti-Patterns (Block PR)

### No Assertions
```python
# ❌ Test proves nothing
def test_user_creation():
    user = create_user("alice@example.com")
    # No assertion!
```

**Fix:** Add meaningful assertions that verify behavior.

### Mocking the Subject Under Test
```python
# ❌ Circular logic - testing the mock, not the code
def test_calculator(mocker):
    mocker.patch("calculator.add", return_value=5)
    assert calculator.add(2, 3) == 5  # Always passes!
```

**Fix:** Mock collaborators, not the thing you're testing.

### Testing Framework Code
```python
# ❌ Testing Django/pytest, not your code
def test_django_orm_works():
    user = User.objects.create(name="test")
    assert User.objects.get(id=user.id).name == "test"
```

**Fix:** Test your domain logic, trust the framework.

### Flaky Time Dependencies
```python
# ❌ Fails on slow CI or at midnight
def test_created_today():
    item = create_item()
    assert item.created_at.date() == datetime.now().date()
```

**Fix:** Inject time as dependency or use freezegun.

---

## Significant Anti-Patterns (Request Changes)

### Multiple Behaviors in One Test
```python
# ❌ Which behavior failed?
def test_user_service():
    # Tests creation
    user = service.create_user("alice@example.com")
    assert user.id is not None

    # Tests update
    service.update_user(user.id, name="Alice")
    assert user.name == "Alice"

    # Tests deletion
    service.delete_user(user.id)
    assert User.objects.count() == 0
```

**Fix:** Split into separate focused tests.

### Shared Mutable State
```python
# ❌ Tests affect each other
users = []

def test_add_user():
    users.append(User("alice"))
    assert len(users) == 1

def test_add_another():
    users.append(User("bob"))
    assert len(users) == 1  # Fails if test_add_user ran first!
```

**Fix:** Use fixtures with proper isolation/cleanup.

### Deep Mock Chains
```python
# ❌ Coupled to implementation structure
mock_client.session.get.return_value.json.return_value.get.return_value = data
```

**Fix:** Redesign interface or mock at higher level.

### Patching Wrong Location
```python
# ❌ Patches where defined, not where used
# In mymodule.py: from requests import get
mocker.patch("requests.get")  # Won't work!
```

**Fix:** Patch where the name is looked up: `mocker.patch("mymodule.get")`

### Over-Mocking
```python
# ❌ Test doesn't exercise real code
def test_process_order(mocker):
    mocker.patch("orders.validate_order", return_value=True)
    mocker.patch("orders.calculate_total", return_value=100)
    mocker.patch("orders.apply_discount", return_value=90)
    mocker.patch("orders.save_order", return_value=Order(id=1))

    result = process_order(order_data)
    assert result.id == 1  # Proves nothing about real code
```

**Fix:** Test real code with minimal, appropriate mocking.

### Missing Mock Verification
```python
# ❌ Mock exists but interaction never verified
def test_sends_notification(mocker):
    mock_sender = mocker.patch("notifications.send")
    service.complete_order(order)
    # Never checks if send was called!
```

**Fix:** Add `mock_sender.assert_called_once_with(...)`.

### Asserting on Private State
```python
# ❌ Coupled to implementation
def test_processor():
    processor = DataProcessor()
    processor.process(data)
    assert processor._internal_cache == {...}  # Private!
```

**Fix:** Assert on public behavior/output instead.

### Magic Numbers
```python
# ❌ What do these numbers mean?
def test_calculation():
    result = calculate(42, 17, 3.14)
    assert result == 2.847
```

**Fix:** Use named constants or parameterized tests with descriptive names.

---

## Minor Anti-Patterns (Suggest Improvement)

### Duplicate Test Setup
```python
# Could be DRYer with fixtures
def test_case_1():
    client = Client()
    client.connect("localhost", 8080)
    client.authenticate("user", "pass")
    ...

def test_case_2():
    client = Client()
    client.connect("localhost", 8080)
    client.authenticate("user", "pass")
    ...
```

**Fix:** Extract to fixture, but balance DRY vs. readability.

### Unclear Test Names
```python
# ❌ What behavior is this testing?
def test_order_1():
    ...

def test_process():
    ...
```

**Fix:** `test_applies_discount_when_customer_is_premium`

### Unnecessary Precision
```python
# ❌ Exact float comparison
assert result == 3.141592653589793
```

**Fix:** Use `pytest.approx()`: `assert result == pytest.approx(3.14, rel=1e-2)`

### Missing Parameterization
```python
# Repetitive similar tests
def test_validates_email_with_at():
    assert is_valid("user@domain.com")

def test_validates_email_without_at():
    assert not is_valid("userdomain.com")

def test_validates_empty_email():
    assert not is_valid("")
```

**Fix:** Use `@pytest.mark.parametrize`.

---

## Organization Anti-Patterns

### Giant Test Files
One file with hundreds of unrelated tests.

**Fix:** Organize by feature/module, one test class per concept.

### No Test Hierarchy
All tests in one flat directory.

**Fix:** Organize into unit/integration/acceptance directories.

### Fixtures Everywhere
Fixtures scattered across many conftest.py files, hard to trace.

**Fix:** Centralize in root conftest.py or use factory functions.

### Missing Markers
No way to run subsets of tests.

**Fix:** Add markers: `@pytest.mark.slow`, `@pytest.mark.integration`.

---

## Mocking-Specific Anti-Patterns

### Mocking Value Objects
```python
# ❌ Don't mock simple data
mock_date = mocker.Mock()
mock_date.year = 2024
```

**Fix:** Use real value objects.

### Mocking Libraries You Don't Own
```python
# ❌ Fragile to library updates
mocker.patch("pandas.DataFrame.to_csv")
```

**Fix:** Wrap in adapter, mock the adapter.

### Mock Without Return Value
```python
# ❌ Returns Mock object, probably not intended
mock_service = mocker.patch("service.get_data")
result = process()  # result contains Mock, not data
```

**Fix:** Set `return_value` or `side_effect`.

### Forgetting to Stop Patches
```python
# ❌ Leaks across tests (when not using pytest-mock)
patcher = patch("module.function")
mock = patcher.start()
# Test runs... but patcher.stop() never called
```

**Fix:** Use `pytest-mock` fixtures or context managers.
