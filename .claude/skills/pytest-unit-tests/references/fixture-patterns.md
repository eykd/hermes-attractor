# Advanced Pytest Fixture Patterns

## Scope Hierarchy and Execution Order

```
Session fixtures (once per test run)
  └── Module fixtures (once per file)
        └── Class fixtures (once per class)
              └── Function fixtures (once per test)
```

Setup occurs top-down; teardown occurs bottom-up.

## Pattern: Fixture with Parameters

```python
@pytest.fixture(params=["sqlite", "postgres"])
def database(request):
    if request.param == "sqlite":
        db = SQLiteDB(":memory:")
    else:
        db = PostgresDB("test_db")
    yield db
    db.close()

# Test runs twice: once with sqlite, once with postgres
def test_crud_operations(database):
    database.insert({"id": 1})
    assert database.get(1) is not None
```

## Pattern: Indirect Parameterization

```python
@pytest.fixture
def user(request):
    role = request.param
    return User(name="Test", role=role)

@pytest.mark.parametrize("user", ["admin", "member", "guest"], indirect=True)
def test_permissions(user):
    if user.role == "admin":
        assert user.can_delete()
```

## Pattern: Dynamic Fixture Selection

```python
@pytest.fixture
def dev_db():
    return Database(host="dev.db")

@pytest.fixture
def prod_db():
    return Database(host="prod.db")

@pytest.mark.parametrize("db_name", ["dev_db", "prod_db"])
def test_connection(db_name, request):
    db = request.getfixturevalue(db_name)
    assert db.ping()
```

## Pattern: Fixture Composition

```python
@pytest.fixture
def user():
    return User(name="Alice")

@pytest.fixture
def cart(user):
    return Cart(owner=user)

@pytest.fixture
def order(cart):
    return Order(cart=cart)

def test_order_total(order):
    # order depends on cart depends on user
    assert order.total >= 0
```

## Pattern: Autouse for Global Setup

```python
@pytest.fixture(autouse=True)
def reset_singletons():
    """Runs before every test automatically."""
    GlobalConfig.reset()
    yield
    GlobalConfig.reset()

@pytest.fixture(autouse=True, scope="session")
def setup_test_environment():
    """Runs once at session start."""
    os.environ["TESTING"] = "true"
    yield
    del os.environ["TESTING"]
```

## Pattern: Request Context Access

```python
@pytest.fixture
def logger(request):
    """Logger that includes test name."""
    log = Logger(name=request.node.name)
    yield log
    log.flush()

@pytest.fixture
def temp_file(request, tmp_path):
    """Create temp file named after test."""
    path = tmp_path / f"{request.node.name}.txt"
    path.touch()
    return path
```

## Pattern: Finalizers for Complex Teardown

```python
@pytest.fixture
def resource_pool(request):
    pool = ResourcePool()

    def cleanup():
        pool.drain()
        pool.close()

    request.addfinalizer(cleanup)
    return pool
```

## Pattern: Shared Base Fixture with Different Scopes

```python
from contextlib import contextmanager

@contextmanager
def _database_connection():
    """Base logic shared across scopes."""
    conn = Database.connect()
    yield conn
    conn.close()

@pytest.fixture(scope="function")
def db():
    with _database_connection() as conn:
        yield conn

@pytest.fixture(scope="session")
def shared_db():
    with _database_connection() as conn:
        yield conn
```

## Pattern: Conditional Fixtures

```python
@pytest.fixture
def api_client(request):
    if hasattr(request, "param") and request.param == "authenticated":
        client = APIClient()
        client.login("test_user", "password")
    else:
        client = APIClient()
    return client
```

## Pattern: Fixture for Test Data Files

```python
@pytest.fixture
def test_data_dir():
    return Path(__file__).parent / "data"

@pytest.fixture
def sample_csv(test_data_dir):
    return test_data_dir / "sample.csv"

@pytest.fixture
def load_json(test_data_dir):
    def _load(filename):
        with open(test_data_dir / filename) as f:
            return json.load(f)
    return _load
```

## Fixture Scope Decision Matrix

| Scenario | Recommended Scope |
|----------|-------------------|
| Simple data creation | `function` |
| Database with transaction rollback | `function` |
| Read-only shared data | `module` or `session` |
| Expensive external connection | `session` |
| Browser for UI tests | `class` or `module` |
| In-memory cache | `session` |

## Fixture Troubleshooting

**"Fixture not found"**
- Check fixture is in conftest.py or same file
- Verify conftest.py is in correct directory
- Ensure function has `@pytest.fixture` decorator

**"Fixture has wrong scope"**
- Higher-scoped fixture can't depend on lower-scoped
- Session can't use function-scoped fixture

**"Fixture runs too many times"**
- Check scope matches intended lifecycle
- Use `scope="session"` for expensive one-time setup

**"Fixture state bleeds between tests"**
- Ensure proper teardown after yield
- Avoid mutable default arguments
- Reset global state in autouse fixture
