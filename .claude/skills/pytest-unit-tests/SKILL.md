---
name: pytest-unit-tests
description: "Use when: (1) Writing unit tests for single functions/classes in isolation, (2) Testing without external dependencies (no DB/network/filesystem), (3) Implementing TDD workflows, (4) Debugging flaky tests, (5) Questions about test design or best practices."
---

# Effective Unit Testing with Pytest

## Core Philosophy

Tests should be **sensitive to behavior** but **insensitive to structure**. When code behavior changes, tests fail. When you refactor without changing behavior, tests pass.

## Test Desiderata: 12 Properties of Good Tests

Unit tests should embody Kent Beck's Test Desiderata principles: **Behavioral, Structure-insensitive, Readable, Writable, Fast, Deterministic, Automated, Isolated, Composable, Specific, Predictive, and Inspiring**.

Key principles for unit tests:
- **Behavioral**: Test public interfaces, not private methods
- **Isolated**: Fresh fixtures per test, no shared mutable state
- **Fast**: Mock I/O boundaries, run entirely in memory
- **Deterministic**: Control time, randomness, and external state

For complete Test Desiderata guidance, see [references/test-desiderata.md](references/test-desiderata.md).

## Test Structure: Arrange-Act-Assert

```python
def test_user_receives_discount_when_loyal():
    # Arrange: Set up preconditions
    customer = Customer(loyalty_years=5)
    cart = Cart(items=[Item(price=100)])

    # Act: Execute the behavior
    total = checkout(cart, customer)

    # Assert: Verify the outcome
    assert total == 90  # 10% loyalty discount
```

## Naming Convention

Name tests as behavior descriptions:
```python
# Good: Describes behavior
def test_expired_subscription_cannot_access_premium_content(): ...
def test_order_total_includes_tax_for_california(): ...

# Bad: Describes implementation
def test_calculate(): ...
def test_user_method(): ...
```

## Fixtures Overview

Unit tests use fixtures for test data setup. Use `function` scope (default) for isolation.

```python
@pytest.fixture
def user():
    return User(name="Test User", email="test@example.com")

def test_user_can_login(user):
    assert user.authenticate("password")
```

For comprehensive fixture patterns (scopes, factories, composition, autouse), see **[pytest-fixtures](../pytest-fixtures/SKILL.md)**.

## Mocking Overview

Mock external boundaries in unit tests: I/O, time, randomness, external services.

```python
def test_sends_notification(mocker):
    mock_send = mocker.patch("app.email.send")
    notify_user(user_id=1)
    mock_send.assert_called_once()
```

For comprehensive mocking patterns (when to mock, pytest-mock, monkeypatch, AsyncMock), see **[pytest-mocking](../pytest-mocking/SKILL.md)**.

## Exception Testing

```python
def test_invalid_input_raises():
    with pytest.raises(ValueError, match="must be positive"):
        calculate(-1)
```

## Test Layers

### Unit Tests
- No database, network, or filesystem
- Test single function/method/class
- Run entirely in memory
- Express behavior in domain language

### Integration Tests
- Use real infrastructure (test DB)
- Test one boundary per test file
- Verify adapters work with real systems

### Acceptance Tests
- Use HTTP client as entry point
- Hit real URL routing and templates
- Assert on user-visible outcomes

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Testing private methods | Couples to implementation | Test via public interface |
| Multiple behaviors per test | Unclear failures | One assertion focus per test |
| Shared mutable state | Test interdependence | Fresh fixtures per test |
| Over-mocking | Tests pass but prod fails | Mock only boundaries |
| Complex setup | Design smell | Simplify production code |
| Flaky tests | Erodes trust | Control all external inputs |

## Determinism Checklist

Eliminate these sources of flakiness:
- [ ] Random data → Use fixed seeds or explicit values
- [ ] Current time → Use `freezegun` or inject time
- [ ] External APIs → Mock responses
- [ ] Database state → Fresh DB per test or transaction rollback
- [ ] File system → Use `tmp_path` fixture
- [ ] Test order → Ensure complete isolation

## TDD Workflow (Red-Green-Refactor)

1. **RED**: Write failing test for new behavior
2. **GREEN**: Write minimum code to pass
3. **REFACTOR**: Improve code, keep tests green
4. Repeat

## When to Use This Skill

**Choose pytest-unit-tests when:**
- Writing tests for single functions, classes, or methods in isolation
- Testing business logic without external dependencies (database, network, filesystem)
- Implementing TDD (red-green-refactor) workflow
- Tests run entirely in memory and complete in milliseconds
- Debugging test design or organization issues

**Use a different skill when:**
- Testing database repositories or ORM behavior → **pytest-integration-tests**
- Testing complete user workflows via HTTP → **pytest-acceptance-tests**
- Need fixture patterns (scopes, factories, composition) → **pytest-fixtures**
- Need mocking guidance (monkeypatch, pytest-mock) → **pytest-mocking**
- Need parametrization patterns (data-driven testing) → **pytest-parametrize**
- Testing async code (coroutines, asyncio) → **pytest-async-testing**

## Quick Decision Guide

**"Is this a unit test?"**
- ✅ Tests single function/class/method
- ✅ Runs entirely in memory (no real DB/network/filesystem)
- ✅ Mocks external boundaries
- ✅ Completes in milliseconds
- ❌ If it touches real infrastructure → Use pytest-integration-tests

**"Should I mock this?"**
- External service/API? → Yes
- Database in unit test? → Yes (or use in-memory)
- Value object or domain logic? → No, use real object
- Time or randomness? → Yes (use freezegun, fixed seeds)

**"Why is my test hard to write?"**
- Too many dependencies? → Refactor production code
- Complex setup? → Extract smaller units
- Need to mock internals? → Redesign interfaces

## Related Skills

This skill focuses on unit test fundamentals. For specialized testing needs, see:

- **[pytest-fixtures](../pytest-fixtures/SKILL.md)**: Fixture scopes, factory patterns, conftest.py organization
- **[pytest-mocking](../pytest-mocking/SKILL.md)**: Comprehensive mocking with pytest-mock and monkeypatch
- **[pytest-parametrize](../pytest-parametrize/SKILL.md)**: Data-driven testing with @pytest.mark.parametrize
- **[pytest-integration-tests](../pytest-integration-tests/SKILL.md)**: Testing boundaries with real infrastructure
- **[pytest-acceptance-tests](../pytest-acceptance-tests/SKILL.md)**: End-to-end user workflow testing
- **[pytest-async-testing](../pytest-async-testing/SKILL.md)**: Testing async/await code and coroutines

## References

For deeper unit testing guidance:

- **[test-desiderata.md](references/test-desiderata.md)**: Kent Beck's 12 Test Desiderata properties with examples
- **[goos-workflow.md](references/goos-workflow.md)**: Outside-in TDD and ports-and-adapters testing strategy
