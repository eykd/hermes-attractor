# Database Integration Testing Patterns

## Core Principles

1. **Use real ORM and schema** — No in-memory fakes for the database layer
2. **Transaction rollback** — Each test undoes its changes automatically
3. **Factory fixtures** — Create data with sensible defaults
4. **One boundary per file** — Test one repository/adapter per test module

## Session and Engine Fixtures

### SQLAlchemy/SQLModel Pattern

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = "sqlite:///./test.db"  # Or PostgreSQL

@pytest.fixture(scope="session")
def engine():
    """Create database engine once per test session."""
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # SQLite only
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """Transactional isolation: rollback after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
```

### Why Transaction Rollback?

- **Isolation**: Each test starts with known state
- **Speed**: No need to truncate tables or recreate schema
- **Simplicity**: Automatic cleanup, no manual teardown

## Factory Fixtures

### Basic Factory Pattern

```python
@pytest.fixture
def user_factory(db_session):
    """Factory for creating User instances."""
    created = []

    def _create(
        email: str = None,
        name: str = "Test User",
        is_active: bool = True,
    ):
        email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
        user = User(email=email, name=name, is_active=is_active)
        db_session.add(user)
        db_session.commit()
        created.append(user)
        return user

    return _create
```

### Factory with Dependencies

```python
@pytest.fixture
def order_factory(db_session, user_factory):
    """Factory for creating Order instances with optional customer."""
    def _create(customer=None, items=None, status="pending"):
        customer = customer or user_factory()
        order = Order(customer_id=customer.id, status=status)

        if items:
            for item_data in items:
                order.items.append(OrderItem(**item_data))

        db_session.add(order)
        db_session.commit()
        return order

    return _create
```

### Build vs Create Pattern

```python
@pytest.fixture
def user_factory(db_session):
    def _factory(email=None, **kwargs):
        defaults = {"name": "Test User", "is_active": True}
        defaults.update(kwargs)
        email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
        return User(email=email, **defaults)

    def _build(**kwargs):
        """Return unsaved instance."""
        return _factory(**kwargs)

    def _create(**kwargs):
        """Return saved instance."""
        user = _factory(**kwargs)
        db_session.add(user)
        db_session.commit()
        return user

    _create.build = _build
    return _create

# Usage:
def test_with_saved_user(user_factory):
    user = user_factory()  # Saved to DB

def test_with_unsaved_user(user_factory):
    user = user_factory.build()  # Not saved
```

## Repository Integration Tests

### Testing CRUD Operations

```python
# tests/integration/test_user_repository_integration.py
import pytest

pytestmark = pytest.mark.integration


class TestUserRepository:
    """Integration tests for UserRepository."""

    def test_saves_and_retrieves_user(self, user_repository, db_session):
        # Given
        user = User(email="alice@example.com", name="Alice")

        # When
        user_repository.save(user)
        loaded = user_repository.get_by_email("alice@example.com")

        # Then
        assert loaded is not None
        assert loaded.id is not None
        assert loaded.email == "alice@example.com"
        assert loaded.name == "Alice"

    def test_returns_none_for_nonexistent_user(self, user_repository):
        loaded = user_repository.get_by_email("nobody@example.com")
        assert loaded is None

    def test_finds_users_by_status(self, user_repository, user_factory):
        # Given
        user_factory(is_active=True)
        user_factory(is_active=True)
        user_factory(is_active=False)

        # When
        active_users = user_repository.find_by_status(is_active=True)

        # Then
        assert len(active_users) == 2
        assert all(u.is_active for u in active_users)
```

### Testing Constraints and Edge Cases

```python
def test_raises_on_duplicate_email(user_repository, user_factory):
    # Given
    user_factory(email="taken@example.com")

    # When/Then
    duplicate = User(email="taken@example.com", name="Imposter")
    with pytest.raises(IntegrityError):
        user_repository.save(duplicate)


def test_handles_null_optional_fields(user_repository):
    user = User(email="minimal@example.com", name=None, bio=None)
    user_repository.save(user)

    loaded = user_repository.get_by_email("minimal@example.com")
    assert loaded.name is None
    assert loaded.bio is None
```

### Testing Complex Queries

```python
def test_finds_orders_with_total_above_threshold(
    order_repository, user_factory, order_factory
):
    # Given
    customer = user_factory()
    order_factory(customer=customer, total=50.00)
    order_factory(customer=customer, total=150.00)
    order_factory(customer=customer, total=200.00)

    # When
    expensive_orders = order_repository.find_with_total_above(100.00)

    # Then
    assert len(expensive_orders) == 2
    assert all(o.total > 100 for o in expensive_orders)


def test_aggregates_customer_spending(order_repository, user_factory, order_factory):
    # Given
    alice = user_factory(name="Alice")
    bob = user_factory(name="Bob")
    order_factory(customer=alice, total=100)
    order_factory(customer=alice, total=200)
    order_factory(customer=bob, total=50)

    # When
    spending = order_repository.get_customer_total_spending(alice.id)

    # Then
    assert spending == 300.00
```

## Handling Database-Specific Behavior

### PostgreSQL vs SQLite Differences

```python
@pytest.fixture(scope="session")
def database_url(request):
    """Get database URL from command line or use SQLite default."""
    return request.config.getoption(
        "--database-url",
        default="sqlite:///./test.db"
    )


def pytest_addoption(parser):
    parser.addoption(
        "--database-url",
        action="store",
        default="sqlite:///./test.db",
        help="Database URL for integration tests"
    )
```

### Testing JSON Fields (PostgreSQL)

```python
@pytest.mark.skipif(
    "sqlite" in DATABASE_URL,
    reason="JSON operations require PostgreSQL"
)
def test_json_field_query(user_repository, user_factory):
    user_factory(preferences={"theme": "dark", "notifications": True})
    user_factory(preferences={"theme": "light", "notifications": False})

    dark_theme_users = user_repository.find_by_preference("theme", "dark")
    assert len(dark_theme_users) == 1
```

## Testing Transactions and Concurrency

### Optimistic Locking

```python
def test_detects_concurrent_modification(order_repository, order_factory):
    # Given: Same order loaded in two "sessions"
    order = order_factory(version=1)

    order_v1 = order_repository.get_by_id(order.id)
    order_v2 = order_repository.get_by_id(order.id)

    # When: First session updates
    order_v1.status = "shipped"
    order_repository.save(order_v1)

    # Then: Second session's stale update fails
    order_v2.status = "cancelled"
    with pytest.raises(StaleDataError):
        order_repository.save(order_v2)
```

### Testing Rollback Behavior

```python
def test_rollback_on_error(db_session, user_repository):
    # Given
    user = User(email="test@example.com")
    user_repository.save(user)

    # When: Operation fails mid-transaction
    try:
        user.email = "invalid"  # Will fail constraint
        db_session.commit()
    except IntegrityError:
        db_session.rollback()

    # Then: Original state preserved
    loaded = user_repository.get_by_email("test@example.com")
    assert loaded is not None
```

## Performance Considerations

### Connection Pooling

```python
@pytest.fixture(scope="session")
def engine():
    return create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Verify connections
    )
```

### Bulk Operations

```python
def test_bulk_insert_performance(user_repository, db_session):
    users = [User(email=f"user{i}@example.com") for i in range(1000)]

    # Use bulk insert for performance
    db_session.bulk_save_objects(users)
    db_session.commit()

    assert user_repository.count() == 1000
```

## Cleanup Strategies

### Transaction Rollback (Preferred)

```python
@pytest.fixture(scope="function")
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()  # Automatic cleanup
    connection.close()
```

### Explicit Truncation (When Needed)

```python
@pytest.fixture(scope="function")
def clean_db(db_session):
    yield db_session
    # After test: truncate all tables
    for table in reversed(Base.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()
```

## Common Pitfalls

| Pitfall | Symptom | Solution |
|---------|---------|----------|
| Missing rollback | Tests affect each other | Use transaction fixture |
| Caching issues | Stale data in tests | Clear session after commit |
| Foreign key order | Constraint violations | Use factory dependencies |
| Connection exhaustion | "Too many connections" | Use connection pooling |
| Slow tests | Long test suite | Use `session` scope for engine |
