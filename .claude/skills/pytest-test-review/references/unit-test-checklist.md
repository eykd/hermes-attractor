# Unit Test Review Checklist

Detailed checklist for reviewing pytest unit tests following GOOS principles.

## Purpose
A unit test defines **one object's behavior in isolation**, driving the emergence of roles, messages, and collaborations.

## Required Criteria

### Structure
- [ ] File under `tests/unit/` or clearly organized unit test location
- [ ] Test class groups related tests for a function/object
- [ ] Test method name describes behavior in domain terms
- [ ] Clear Arrange–Act–Assert structure

### Isolation
- [ ] No database queries
- [ ] No network calls
- [ ] No filesystem operations
- [ ] No external service dependencies
- [ ] Runs in milliseconds

### Focus
- [ ] Tests single behavior of single object
- [ ] One logical assertion per test
- [ ] Minimal, intention-revealing setup

### Mocking
- [ ] Mocks only roles/interfaces, not concrete classes
- [ ] Does not mock value objects or data structures
- [ ] Mock interactions verified (assert_called, etc.)
- [ ] No deep mock chains

### Assertions
- [ ] Assertions on public behavior, not private state
- [ ] Assertions specific enough to catch regressions
- [ ] Meaningful failure messages

## Red Flags

### Critical (Block PR)
- Test has no assertions
- Test hits real database or network
- Test mocks the subject under test
- Test name is meaningless (`test_1`, `test_it_works`)

### Significant (Request Changes)
- Multiple unrelated behaviors in one test
- Setup code longer than 20 lines for simple behavior
- Asserting on private attributes (`obj._internal`)
- Mock created but never verified
- Exact sequence assertions when order doesn't matter

### Minor (Suggest Improvement)
- Could use parameterization for similar cases
- Test name could be more descriptive
- Magic numbers without explanation

## Good Example

```python
class TestOrderProcessor:
    def test_applies_discount_for_premium_customer(self, mocker):
        # Arrange
        discount_service = mocker.Mock()
        discount_service.calculate.return_value = Decimal("10.00")
        processor = OrderProcessor(discount_service)
        order = Order(total=Decimal("100.00"), customer_type="premium")

        # Act
        result = processor.process(order)

        # Assert
        assert result.final_total == Decimal("90.00")
        discount_service.calculate.assert_called_once_with(order)
```

**Why it's good:**
- Clear test name describes behavior
- Minimal setup with only relevant data
- Mocks a role (discount_service), not concrete class
- Verifies both outcome and collaboration
- Single behavior tested

## Bad Example

```python
def test_order(db_session, mocker):
    mocker.patch("orders.datetime").now.return_value = datetime(2024, 1, 1)
    mocker.patch("orders.requests.post").return_value.json.return_value = {"rate": 0.1}
    user = User(name="test", email="test@test.com", address="123 Main St")
    db_session.add(user)
    db_session.commit()
    order = Order(user_id=user.id, items=[...], status="pending")
    db_session.add(order)
    db_session.commit()

    result = process_order(order.id)

    assert result is not None
    assert result.status == "completed"
    assert result.total > 0
    assert user.orders.count() == 1
```

**Why it's bad:**
- Hits real database (not a unit test)
- Patches third-party library directly
- Deep mock chain
- Too much setup for unclear behavior
- Multiple behaviors tested
- Vague assertions (`is not None`, `> 0`)
- Test name doesn't describe behavior
