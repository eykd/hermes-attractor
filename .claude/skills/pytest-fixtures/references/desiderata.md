# Kent Beck's Test Desiderata and Fixture Design

How fixture design decisions impact test quality properties.

## The 12 Desiderata

Kent Beck identified 12 desirable properties of tests. Fixture design directly impacts many of these.

## Desiderata That Fixtures Affect

### 1. Isolated (Desideratum #8)

**Principle**: Tests should be isolated from each other. Whether one test passes or fails should have no effect on other tests.

**Fixture implications**:
- Default to `function` scope for maximum isolation
- When using broader scopes, ensure fixtures are read-only or properly reset
- Always clean up resources in teardown
- Never rely on test execution order

**Good**:
```python
@pytest.fixture
def user():
    user = User.create(name="Test")
    yield user
    user.delete()  # Cleanup ensures isolation
```

**Bad**:
```python
@pytest.fixture(scope="session")
def users():
    return []  # Mutable shared state - tests pollute each other
```

### 2. Fast (Desideratum #5)

**Principle**: Tests under one second feel instantaneous. Slow tests break developer flow.

**Fixture implications**:
- Share expensive resources with broader scopes when isolation allows
- Use in-memory alternatives (SQLite, fakes) for unit tests
- Consider lazy initialization for rarely-used expensive fixtures
- Profile fixture setup time if tests feel slow

**Trade-off decision**:
```
If setup < 100ms → function scope (favor isolation)
If setup > 100ms and read-only → module/session scope (favor speed)
If setup > 100ms and mutable → function scope (accept cost for isolation)
```

### 3. Deterministic (Desideratum #6)

**Principle**: Tests should always produce the same result when run with the same inputs. Flaky tests erode trust.

**Fixture implications**:
- Avoid `random` without explicit seeds
- Control time-dependent behavior with freezegun or mocks
- Don't depend on external services (use fakes/mocks)
- Ensure database state is predictable

**Good**:
```python
@pytest.fixture
def random_user(request):
    # Seed based on test name for reproducibility
    seed = hash(request.node.name)
    random.seed(seed)
    return User(name=f"User_{random.randint(1, 1000)}")
```

**Bad**:
```python
@pytest.fixture
def user():
    # Non-deterministic - different each run
    return User(name=f"User_{random.randint(1, 1000)}")
```

### 4. Composable (Desideratum #9)

**Principle**: Test components separately and trust they compose correctly. Avoid testing every combination.

**Fixture implications**:
- Design small, focused fixtures
- Use fixture dependency injection to compose
- Avoid monolithic "everything" fixtures
- Factory fixtures enable flexible composition

**Good**:
```python
@pytest.fixture
def user():
    return User()

@pytest.fixture
def cart(user):
    return Cart(owner=user)

@pytest.fixture
def order(cart, product):
    return Order(cart=cart, items=[product])
```

**Bad**:
```python
@pytest.fixture
def everything():
    user = User()
    cart = Cart(owner=user)
    product = Product()
    order = Order(cart=cart, items=[product])
    return {"user": user, "cart": cart, "product": product, "order": order}
```

### 5. Readable (Desideratum #3)

**Principle**: Tests should function as self-contained stories. They're read far more often than written.

**Fixture implications**:
- Use intention-revealing names
- Keep fixture logic simple and obvious
- Avoid deep nesting or complex dependencies
- Document non-obvious fixtures

**Naming guide**:
| Bad | Good |
|-----|------|
| `data` | `valid_checkout_data` |
| `obj` | `pending_order` |
| `f1` | `authenticated_user` |
| `setup` | `empty_shopping_cart` |

### 6. Structure-Insensitive (Desideratum #2)

**Principle**: Tests should remain unchanged when code structure changes (refactoring).

**Fixture implications**:
- Set up behavioral contexts, not implementation details
- Don't expose internal object structure
- Fixtures should survive refactoring of production code

**Good**:
```python
@pytest.fixture
def user_who_can_checkout():
    """Behavioral context - what the user CAN DO"""
    user = User()
    user.verify_email()
    user.add_payment_method()
    return user
```

**Bad**:
```python
@pytest.fixture
def user_with_verified_flag_and_payment_id():
    """Implementation detail - HOW it's stored"""
    return User(_email_verified=True, _payment_method_id=123)
```

### 7. Writable (Desideratum #4)

**Principle**: Tests should be easy to write. Difficulty indicates design problems.

**Fixture implications**:
- If fixtures require extensive setup, reconsider production code design
- Factory fixtures reduce boilerplate
- Use sensible defaults with override capability

**Good**:
```python
@pytest.fixture
def create_user():
    def _create(name="Default", email="test@test.com", **kwargs):
        return User(name=name, email=email, **kwargs)
    return _create

def test_something(create_user):
    user = create_user(role="admin")  # Easy to write
```

## Desiderata Trade-offs in Fixtures

Sometimes properties conflict. Here's how to navigate:

### Isolated vs Fast

**Scenario**: Database setup takes 500ms per test.

**Resolution options**:
1. Module scope with transaction rollback (preserves isolation)
2. Session scope with careful test design (read-only tests)
3. In-memory database (faster setup)
4. Accept the cost for critical tests

```python
# Option 1: Transaction rollback
@pytest.fixture
def db_session(database):
    transaction = database.begin()
    yield database
    transaction.rollback()  # Fast reset, good isolation
```

### Deterministic vs Readable

**Scenario**: Realistic test data needs variety but must be reproducible.

**Resolution**: Seed-based factories with clear naming.

```python
@pytest.fixture
def realistic_users(request):
    """Generates varied but reproducible user data."""
    fake = Faker()
    fake.seed_instance(hash(request.node.name))

    return [
        User(name=fake.name(), email=fake.email())
        for _ in range(5)
    ]
```

### Composable vs Readable

**Scenario**: Deep fixture chains obscure what's being tested.

**Resolution**: Flatten for tests, compose for reuse.

```python
# For reuse - composable
@pytest.fixture
def order_with_items(create_order, create_product):
    order = create_order()
    order.add(create_product(price=10))
    order.add(create_product(price=20))
    return order

# For clarity - explicit in test
def test_order_total(create_order, create_product):
    order = create_order()
    order.add(create_product(price=10))
    order.add(create_product(price=20))
    assert order.total == 30  # Clear what's being tested
```

## Checklist: Desiderata-Aligned Fixtures

Before finalizing a fixture, verify:

- [ ] **Isolated**: Does teardown restore state completely?
- [ ] **Fast**: Is scope appropriate for setup cost?
- [ ] **Deterministic**: Are all inputs controlled?
- [ ] **Composable**: Can it combine with other fixtures?
- [ ] **Readable**: Does the name reveal intent?
- [ ] **Structure-Insensitive**: Does it describe behavior, not implementation?
- [ ] **Writable**: Is it easy to use with sensible defaults?

## Summary Table

| Desideratum | Fixture Impact | Primary Lever |
|-------------|----------------|---------------|
| Isolated | Avoid test pollution | Scope + teardown |
| Fast | Reduce setup overhead | Scope + alternatives |
| Deterministic | Control all inputs | Seeding + mocks |
| Composable | Small, focused fixtures | Dependency injection |
| Readable | Clear intent | Naming + simplicity |
| Structure-Insensitive | Behavioral setup | Abstraction level |
| Writable | Low friction | Factories + defaults |
