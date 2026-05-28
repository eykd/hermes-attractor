# Integration Test Review Checklist

Detailed checklist for reviewing pytest integration tests following GOOS principles.

## Purpose
An integration test verifies that **adapters correctly interact with real external systems**, exercising boundaries without mocking them.

## Required Criteria

### Structure
- [ ] File under `tests/integration/` or clearly organized integration location
- [ ] `pytestmark = pytest.mark.django_db` when DB involved
- [ ] Clear Given–When–Then structure
- [ ] Tests single integration boundary

### Scope
- [ ] Tests exactly one boundary (repository OR adapter OR gateway)
- [ ] Uses real ORM/database for persistence boundaries
- [ ] Uses controlled fakes/containers for external services
- [ ] Does NOT test domain logic (that's for unit tests)
- [ ] Does NOT test full user workflows (that's for acceptance tests)

### Infrastructure
- [ ] Uses real infrastructure, not mocks of infrastructure
- [ ] External services use controlled fakes (responses, requests_mock)
- [ ] Database state is controlled and repeatable
- [ ] Proper cleanup/rollback after test

### Assertions
- [ ] Asserts on real side effects (DB rows, HTTP payloads, files)
- [ ] Does not assert on internal implementation details
- [ ] Verifies both request sent and response interpreted (for HTTP adapters)

## Red Flags

### Critical (Block PR)
- Mocks the very thing being tested (e.g., mocking repository in repository test)
- Uses Django test client (that's acceptance-level)
- Hits live external services
- Tests domain logic that should be in unit tests

### Significant (Request Changes)
- Tests multiple boundaries in one test
- No database marker when DB is required
- Asserts on private attributes
- Missing cleanup/rollback
- Flaky due to timing or external dependencies

### Minor (Suggest Improvement)
- Could use test containers for more realistic testing
- Fixture could be more intention-revealing
- Could add schema/contract assertions

## Good Example: Repository

```python
# tests/integration/test_user_repository.py
import pytest

pytestmark = pytest.mark.django_db


def test_user_repository_saves_and_retrieves_user(user_repository):
    # Given: a new user
    user = User(email="alice@example.com", name="Alice")

    # When: saved and retrieved
    user_repository.save(user)
    retrieved = user_repository.get_by_email("alice@example.com")

    # Then: data matches
    assert retrieved.email == "alice@example.com"
    assert retrieved.name == "Alice"
    assert retrieved.id is not None
```

**Why it's good:**
- Tests single boundary (repository)
- Uses real database
- Clear Given–When–Then
- Asserts on real persisted state

## Good Example: HTTP Adapter

```python
def test_payment_adapter_handles_successful_charge(payment_adapter, fake_http):
    # Given: gateway returns success
    fake_http.register_uri(
        "POST", "https://api.gateway.com/charge",
        json={"id": "ch_123", "status": "succeeded"}
    )

    # When: we charge
    result = payment_adapter.charge(amount=5000, token="tok_test")

    # Then: correct request sent
    assert fake_http.last_request.json() == {
        "amount": 5000,
        "source": "tok_test"
    }

    # And: response interpreted correctly
    assert result.is_success
    assert result.charge_id == "ch_123"
```

**Why it's good:**
- Uses controlled fake, not live service
- Verifies both outgoing request and response interpretation
- Tests single adapter boundary

## Bad Example

```python
def test_checkout_flow(client, mocker):
    mocker.patch("payments.gateway.charge").return_value = {"status": "ok"}
    mocker.patch("inventory.service.reserve")

    user = create_user()
    client.force_login(user)

    response = client.post("/checkout/", {"item_id": 1})

    assert response.status_code == 302
    assert Order.objects.count() == 1
```

**Why it's bad:**
- Tests full workflow (acceptance-level, not integration)
- Mocks the boundaries instead of testing them
- Uses HTTP client (acceptance pattern)
- Multiple boundaries involved
