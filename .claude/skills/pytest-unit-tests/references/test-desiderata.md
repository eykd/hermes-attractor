# Kent Beck's Test Desiderata: Deep Dive

Detailed explanations and examples for each of the 12 properties.

## 1. Behavioral Sensitivity

Tests must fail when code behavior changes.

```python
# Testing a minimum wage calculator
def test_sf_minimum_wage_applied():
    calc = WageCalculator()
    # SF has $15 minimum wage - if this constant changes, test fails
    result = calc.calculate(hours=40, rate=14, zip="94102")
    assert result == 600  # 40 * $15, not 40 * $14
```

**Diagnostic**: Change a business rule constant. Does a test fail?

## 2. Structure Insensitivity

Tests survive refactoring that doesn't change behavior.

```python
# BAD: Tests internal method (breaks when refactored)
def test_internal():
    calc = Calculator()
    result = calc._apply_sf_rate(14)  # Private method!

# GOOD: Tests public behavior (survives refactoring)
def test_public_behavior():
    calc = Calculator()
    result = calc.calculate(rate=14, location="SF")
```

**Diagnostic**: Inline a method or rename a variable. Do tests break?

## 3. Readability

Tests are self-contained stories.

```python
# BAD: Abstracted away meaning
def test_wage(standard_setup, default_config):
    assert calculate(standard_setup) == EXPECTED_CONSTANT

# GOOD: Full story visible
def test_40_hours_at_15_dollars_pays_600():
    employee = Employee(hours=40, rate=15)
    assert calculate_wage(employee) == 600
```

**Key insight**: DRY hurts test readability. Favor explicit over abstract.

## 4. Writability

Hard-to-write tests reveal design problems.

```python
# Symptom: Excessive setup
def test_simple_calculation():
    config = Config(env="test")
    logger = Logger()
    cache = Cache()
    db = Database(config, logger)
    repo = Repository(db, cache)
    service = Service(repo, logger, config)  # Just to test one method!

# Solution: Simplify production code dependencies
def test_simple_calculation():
    service = Service()  # Defaults to test-friendly config
    assert service.calculate(5) == 25
```

**The Highlighter Test**: Print your test, highlight relevant lines. If most aren't highlighted, your code needs refactoring.

## 5. Speed

Sub-second tests maintain flow state.

| Response Time | Developer Experience |
|---------------|---------------------|
| < 1 second | Feels instant, continuous flow |
| 1-10 seconds | Noticeable, mind wanders |
| > 10 seconds | Context switch, flow broken |

**Techniques**:
- Mock I/O operations
- Use in-memory databases for unit tests
- Separate slow tests with markers
- Run fast tests on every save

## 6. Determinism

Same inputs always produce same outputs.

**Common culprits**:
```python
# BAD: Random data
user = create_user(name=random_name())

# GOOD: Explicit data
user = create_user(name="Alice")

# BAD: Current time
if subscription.expires_at < datetime.now():

# GOOD: Injected time
@freeze_time("2024-01-15")
def test_expiration():
    ...
```

## 7. Automation

No human judgment required to determine pass/fail.

**Anti-pattern**: Tests that require visual inspection
```python
# BAD
def test_output():
    result = generate_report()
    print(result)  # "Check if this looks right"

# GOOD
def test_output():
    result = generate_report()
    assert "Total: $500" in result
    assert result.startswith("Report for")
```

## 8. Isolation

Tests don't affect each other.

```python
# BAD: Shared state
class TestUser:
    user_id = None  # Class variable shared across tests!

    def test_create(self):
        TestUser.user_id = create_user()

    def test_update(self):
        update_user(TestUser.user_id)  # Depends on test_create!

# GOOD: Independent tests
def test_create(fresh_db):
    user_id = create_user()
    assert user_id is not None

def test_update(fresh_db, existing_user):
    update_user(existing_user.id)
```

## 9. Composability

Avoid testing every combination.

```python
# BAD: Combinatorial explosion (4 × 3 × 2 = 24 tests)
def test_visa_admin_express(): ...
def test_visa_admin_standard(): ...
def test_visa_user_express(): ...
# ... 21 more

# GOOD: Test components separately
class TestPaymentMethods:
    def test_visa_charges_correctly(): ...
    def test_mastercard_charges_correctly(): ...

class TestUserPermissions:
    def test_admin_can_refund(): ...
    def test_user_cannot_refund(): ...

class TestShippingMethods:
    def test_express_calculates_correctly(): ...
```

## 10. Specificity

Failure points to exact problem.

```python
# BAD: Which assertion failed?
def test_user():
    user = create_user()
    assert user.name == "Alice"
    assert user.email == "alice@test.com"
    assert user.active == True
    assert user.role == "member"

# GOOD: One focus per test
def test_new_user_is_active():
    user = create_user()
    assert user.active == True

def test_new_user_has_member_role():
    user = create_user()
    assert user.role == "member"
```

## 11. Predictiveness

Tests predict production behavior.

**When prod fails but tests pass**: Write a new test that would have caught it.

```python
# Bug found: Unicode names caused crash
# Add regression test:
def test_unicode_name_handling():
    user = create_user(name="José García-López")
    assert user.display_name == "José García-López"
```

**Limitation**: Some conditions only occur in production (scale, network conditions). Accept that 100% prediction is impossible.

## 12. Inspiration

Tests enable confident action.

With inspiring tests, developers can:
- Delete suspicious code (tests will catch problems)
- Refactor aggressively (safety net in place)
- Deploy without anxiety (green = go)
- Try ambitious changes (tests protect you)

**The goal**: Tests should liberate energy, not consume it.
