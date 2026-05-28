# Kent Beck's Test Desiderata

Detailed guide to the 12 properties of good tests.

## Overview

Not every test needs all 12 properties—some involve trade-offs. Understanding them helps identify what's missing and make conscious decisions.

---

## 1. Behavioral Sensitivity

**Definition:** Tests should fail when the code's behavior changes.

**Review questions:**
- Does the test have meaningful assertions?
- Would the test fail if the expected behavior broke?
- Are assertions specific enough to catch regressions?

**Red flags:**
- No assertions
- Only trivial assertions (`assert result is not None`)
- Assertions that always pass regardless of implementation

**Good pattern:**
```python
# Specific assertion that tests actual behavior
assert calculator.add(2, 3) == 5
```

**Bad pattern:**
```python
# Too vague - doesn't verify correct behavior
assert calculator.add(2, 3) is not None
```

---

## 2. Structure Insensitivity

**Definition:** Tests should survive refactoring that preserves behavior.

**Review questions:**
- Does the test use public interfaces?
- Would renaming a private method break this test?
- Does it test implementation or behavior?

**Red flags:**
- Testing private methods directly
- Assertions on internal state
- Tests that break when code is refactored without behavior change

**Good pattern:**
```python
# Tests through public interface
assert user_service.get_by_email("alice@example.com").name == "Alice"
```

**Bad pattern:**
```python
# Tests internal implementation
assert user_service._cache["alice@example.com"] == user_obj
```

---

## 3. Readable

**Definition:** Tests should be understandable without reading the implementation.

**Review questions:**
- Can you understand the test from its name and structure?
- Does it tell a clear story?
- Is domain vocabulary used?

**Red flags:**
- Excessive abstraction hiding test intent
- Constants extracted to the point of obscuring relationships
- Test names describing implementation, not behavior

**Good pattern:**
```python
def test_premium_customer_receives_twenty_percent_discount():
    customer = Customer(tier="premium")
    order = Order(total=100)

    discounted = apply_discount(order, customer)

    assert discounted.total == 80
```

**Bad pattern:**
```python
def test_discount_1():
    result = process(TEST_DATA_1, CONFIG_A)
    assert result == EXPECTED_1
```

---

## 4. Writable (Easy to Write)

**Definition:** Tests should be easy to write; difficulty signals design problems.

**Review questions:**
- Is setup proportional to what's being tested?
- Does complex setup indicate the code needs redesign?
- Are there many irrelevant parameters?

**Red flags:**
- Hundreds of lines of setup for one assertion
- Tests requiring many objects that aren't relevant
- Complex fixture hierarchies

**Design insight:** If tests are hard to write, the problem is usually with the code's design, not the test.

---

## 5. Fast

**Definition:** Tests should run quickly to encourage frequent execution.

**Review questions:**
- Can unit tests run in milliseconds?
- Are slow tests properly marked and separated?
- Are there unnecessary I/O operations?

**Red flags:**
- Unit tests hitting databases
- Network calls in unit tests
- `time.sleep()` in tests
- Tests taking > 1 second without justification

**Good practice:**
```python
@pytest.mark.slow
def test_full_integration():
    ...  # Slow test clearly marked
```

---

## 6. Deterministic

**Definition:** Tests should always produce the same result.

**Review questions:**
- Does the test rely on current time?
- Is there random data without controlled seeds?
- Could execution order affect results?

**Red flags:**
- `datetime.now()` without freezing
- Random data generation
- Reliance on external services
- Tests that "usually pass"

**Good pattern:**
```python
def test_expiration(freezer):
    freezer.move_to("2024-01-15")
    item = create_item(expires_in_days=7)

    freezer.move_to("2024-01-23")
    assert item.is_expired()
```

---

## 7. Automated

**Definition:** Tests should provide clear pass/fail feedback automatically.

**Review questions:**
- Does it require manual inspection?
- Is there clear pass/fail output?
- Can it run in CI?

**Red flags:**
- Print statements without assertions
- Comments saying "check this manually"
- Tests that require human judgment

---

## 8. Isolated

**Definition:** Tests should be independent of each other.

**Review questions:**
- Can tests run in any order?
- Does each test clean up after itself?
- Is there shared mutable state?

**Red flags:**
- Global variables modified by tests
- Tests that only pass in a specific order
- Missing fixture teardown
- Tests sharing database state without cleanup

**Good pattern:**
```python
@pytest.fixture
def database():
    db = create_test_db()
    yield db
    db.rollback()  # Clean up
```

---

## 9. Composable

**Definition:** Test confidence should compose additively, not multiplicatively.

**Review questions:**
- Are concerns properly separated?
- Is there an N×M explosion of test combinations?
- Can you trust component tests combine correctly?

**Red flags:**
- Tests for every combination of inputs
- Lack of separation between concerns
- Duplicative tests across layers

**Good pattern:**
```python
# Test input validation separately
def test_validates_email_format(): ...

# Test calculation separately
def test_calculates_discount(): ...

# One integration test for happy path
def test_full_order_flow(): ...
```

---

## 10. Specific

**Definition:** Test failures should point to specific problems.

**Review questions:**
- Can you diagnose the issue from the failure message?
- Does the test test one thing?
- Are assertion messages helpful?

**Red flags:**
- Generic failure messages
- Tests that could fail for many different reasons
- Multiple unrelated assertions

**Good pattern:**
```python
assert user.email == "alice@example.com", f"Expected email alice@example.com, got {user.email}"
```

---

## 11. Predictive

**Definition:** Passing tests should predict production success.

**Review questions:**
- Do tests cover realistic scenarios?
- Are edge cases that matter in production covered?
- Are tests over-mocked to the point of not reflecting reality?

**Red flags:**
- Tests that pass but code fails in production
- Excessive mocking hiding real integration issues
- Missing edge cases that occur in real usage

**Insight:** Tests can never be 100% predictive, but gaps should shrink over time.

---

## 12. Inspiring

**Definition:** Tests should give confidence to make changes.

**Review questions:**
- Do developers trust this test suite?
- Do tests enable bold refactoring?
- Do they inspire confidence or anxiety?

**Red flags:**
- Test suite nobody trusts
- Developers afraid to refactor
- Tests that create anxiety

**Goal:** Tests should liberate energy by providing confidence.

---

## Trade-offs

Some properties conflict:

| Trade-off | Resolution |
|-----------|------------|
| Readable vs. DRY | Favor readability in tests |
| Fast vs. Predictive | Separate unit (fast) from integration (predictive) |
| Specific vs. Composable | Test components specifically, compose for coverage |
| Writable vs. Thorough | Let test difficulty guide design improvements |

When properties conflict, make a conscious choice based on context.
