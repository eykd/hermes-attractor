---
name: pytest-integration-tests
description: "Use when: (1) Testing database repositories with real ORM/DB, (2) Testing HTTP adapters with fake servers, (3) Testing message queue adapters, (4) Setting up fixtures with transaction rollback, (5) Questions about testing single boundaries. NOT for complete workflows."
---

# Effective Integration Testing with Pytest

## What is an Integration Test?

An integration test verifies that your code correctly integrates with **one external boundary** using real infrastructure. Integration tests sit between unit tests (pure logic, no infrastructure) and acceptance tests (complete user workflows).

**Test exactly one boundary**:
- Database repository → Real database with test data
- HTTP adapter → Your HTTP client + fake server (responses library)
- Message queue → Your publisher/subscriber + local broker

**Entry point**: Your adapter or repository class (not HTTP endpoints or CLI)

## Test Type Comparison

| Type | Tests What | Entry Point | Infrastructure | Example |
|------|-----------|-------------|----------------|---------|
| **Unit** | Business logic | Function/class | Mocked | `calculate_discount(cart)` |
| **Integration** | Single boundary | Adapter/repository | Real (one boundary) | `UserRepository.save(user)` |
| **Acceptance** | User workflow | HTTP/CLI | Real (full stack) | `POST /checkout` via client |

## Directory Structure

```
tests/
├── conftest.py              # Session fixtures (DB engine, test containers)
├── unit/                    # Pure logic, no infrastructure
├── integration/             # One boundary per test file
│   ├── conftest.py          # Integration fixtures (db_session)
│   ├── test_user_repository.py
│   ├── test_payment_adapter.py
│   └── test_notification_service.py
└── acceptance/              # Complete user workflows
    └── test_checkout_flow.py
```

## Given-When-Then Structure

Every integration test follows this pattern:

```python
def test_order_repository_saves_with_line_items(db_session, order_factory):
    # Given: Initial state
    customer = Customer(email="test@example.com")
    db_session.add(customer)
    db_session.commit()

    order = Order(customer_id=customer.id, items=[
        OrderItem(product_id=1, quantity=2, price=25.00)
    ])

    # When: Execute the boundary operation
    repository = OrderRepository(db_session)
    repository.save(order)

    # Then: Verify the boundary worked
    loaded = repository.get_by_id(order.id)
    assert loaded.customer_id == customer.id
    assert len(loaded.items) == 1
    assert loaded.items[0].quantity == 2
```

## What Integration Tests MUST Do

- ✅ Use **real infrastructure** for the boundary being tested (real database, real HTTP server)
- ✅ Test **exactly one adapter or boundary** per test file
- ✅ Verify the boundary **works correctly** (can save/load, can make HTTP calls, can publish messages)
- ✅ Use **factory fixtures** to create test data
- ✅ **Roll back transactions** or clean up after each test

## What Integration Tests MUST NOT Do

- ❌ Test complete user workflows (that's acceptance testing)
- ❌ Mock the boundary being tested (defeats the purpose)
- ❌ Re-test business logic already covered by unit tests
- ❌ Test multiple boundaries in one test file
- ❌ Call HTTP endpoints or CLI entry points (use adapters directly)

## Database Integration Testing

### Transaction Rollback Pattern

```python
# tests/integration/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

@pytest.fixture(scope="session")
def engine():
    """Create test database engine once per session."""
    return create_engine("postgresql://localhost/test_db")

@pytest.fixture(scope="function")
def db_session(engine):
    """Provide a transactional scope for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()  # Undo all changes
    connection.close()
```

### Factory Fixture for Test Data

```python
@pytest.fixture
def user_factory(db_session):
    """Factory for creating test users."""
    def _create(email=None, name="Test User", **kwargs):
        email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
        user = User(email=email, name=name, **kwargs)
        db_session.add(user)
        db_session.commit()
        return user
    return _create

def test_user_repository_finds_by_email(db_session, user_factory):
    # Given
    user = user_factory(email="alice@example.com")

    # When
    repository = UserRepository(db_session)
    found = repository.find_by_email("alice@example.com")

    # Then
    assert found.id == user.id
    assert found.email == "alice@example.com"
```

## HTTP Adapter Testing

Test your HTTP client code using fake HTTP servers (responses library):

```python
import responses
from myapp.adapters import PaymentAdapter

@responses.activate
def test_payment_adapter_charges_card_successfully():
    # Given: Fake Stripe API response
    responses.add(
        responses.POST,
        "https://api.stripe.com/v1/charges",
        json={"id": "ch_123", "status": "succeeded"},
        status=200
    )

    # When: Our adapter makes HTTP call
    adapter = PaymentAdapter(api_key="test_key")
    result = adapter.charge(amount=5000, token="tok_visa")

    # Then: Adapter correctly parsed response
    assert result.success is True
    assert result.charge_id == "ch_123"

    # Verify HTTP request details
    assert len(responses.calls) == 1
    assert "amount=5000" in responses.calls[0].request.body
```

## Fixture Scopes for Integration Tests

Integration tests typically use:
- `session` scope for expensive infrastructure (DB engine, Docker containers)
- `module` scope for shared setup within one test file
- `function` scope for test data (must be isolated per test)

**Rule**: Wide scope for infrastructure, `function` scope for test data.

For comprehensive fixture patterns and scope selection guidance, see **[pytest-fixtures](../pytest-fixtures/SKILL.md)**.

## Markers for Test Organization

```ini
# pytest.ini
[tool.pytest.ini_options]
markers = [
    "integration: Tests that use real infrastructure (DB, queues)",
    "slow: Tests taking >1 second",
]
```

```bash
# Run only integration tests
pytest -m integration

# Skip slow tests during development
pytest -m "integration and not slow"
```

## When to Use This Skill

**Choose pytest-integration-tests when:**
- Testing database repositories, ORM mappings, or queries
- Testing HTTP adapters (your code making HTTP calls to external services)
- Testing message queue publishers/subscribers
- Verifying one boundary works with real infrastructure
- Need transaction rollback or fixture patterns for infrastructure

**Use a different skill when:**
- Testing business logic without infrastructure → **pytest-unit-tests**
- Testing complete user workflows via HTTP → **pytest-acceptance-tests**
- Need fixture patterns (scopes, factories) → **pytest-fixtures**
- Testing async code → **pytest-async-testing**

## Quick Decision Guide

**"Is this an integration test?"**
- ✅ Tests exactly one boundary (database, HTTP, queue)
- ✅ Uses real infrastructure for that boundary
- ✅ Entry point is adapter/repository (not HTTP endpoint)
- ✅ Focuses on verifying the boundary works, not business logic
- ❌ If testing full user workflow → Use pytest-acceptance-tests
- ❌ If testing pure logic → Use pytest-unit-tests

**"Should I use real database?"**
- Integration test for persistence → Yes
- Unit test for domain logic → No (mock the repository)

**"What fixture scope?"**
- DB engine/Docker containers → `session`
- DB schema setup → `module`
- Test data (users, orders) → `function`

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Mocking the boundary | Tests nothing useful | Use real infrastructure |
| Testing multiple boundaries | Unclear what's being tested | One boundary per test file |
| Shared test data | Tests interfere with each other | Factory fixtures + transaction rollback |
| Testing business logic | Duplicates unit tests | Focus on boundary behavior only |
| Hitting real external APIs | Flaky, slow, costs money | Use responses/httpx_mock for fakes |

## Related Skills

For comprehensive testing coverage, combine with:

- **[pytest-unit-tests](../pytest-unit-tests/SKILL.md)**: Test business logic before testing boundaries. See also Test Desiderata principles in [pytest-unit-tests/references/test-desiderata.md](../pytest-unit-tests/references/test-desiderata.md)
- **[pytest-acceptance-tests](../pytest-acceptance-tests/SKILL.md)**: Test complete user workflows after boundaries work
- **[pytest-fixtures](../pytest-fixtures/SKILL.md)**: Advanced fixture patterns (scopes, composition, factories)
- **[pytest-async-testing](../pytest-async-testing/SKILL.md)**: Testing async database operations
- **[django-pytest-patterns](../django-pytest-patterns/SKILL.md)**: Django-specific testing patterns, fixtures, and test client usage

## References

For detailed integration testing patterns:

- **[database-testing.md](references/database-testing.md)**: Complete database integration patterns
- **[http-testing.md](references/http-testing.md)**: HTTP adapter testing with responses library
