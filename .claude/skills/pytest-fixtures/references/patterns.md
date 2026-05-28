# Pytest Fixture Patterns Reference

Detailed patterns and examples for common fixture scenarios.

## Factory Pattern Variations

### Basic Factory

```python
@pytest.fixture
def create_product():
    def _create(name="Widget", price=10.00, stock=100):
        return Product(name=name, price=price, stock=stock)
    return _create
```

### Factory with Cleanup Tracking

```python
@pytest.fixture
def create_user(database):
    created_ids = []

    def _create(**kwargs):
        user = User(**kwargs)
        database.save(user)
        created_ids.append(user.id)
        return user

    yield _create

    for uid in created_ids:
        database.delete_by_id(uid)
```

### Factory with Defaults from Other Fixtures

```python
@pytest.fixture
def create_order(create_user, create_product):
    def _create(user=None, products=None):
        user = user or create_user()
        products = products or [create_product()]
        return Order(user=user, products=products)
    return _create
```

## Parameterization Patterns

### Direct Parameterization

```python
@pytest.fixture(params=[
    {"role": "admin", "can_delete": True},
    {"role": "editor", "can_delete": False},
    {"role": "viewer", "can_delete": False},
])
def user_permissions(request):
    return request.param
```

### Indirect Parameterization

Pass params through test decorator to fixture:

```python
@pytest.fixture
def configured_client(request):
    config = request.param
    return Client(timeout=config["timeout"], retries=config["retries"])


@pytest.mark.parametrize("configured_client", [
    {"timeout": 5, "retries": 3},
    {"timeout": 30, "retries": 1},
], indirect=True)
def test_client_behavior(configured_client):
    assert configured_client.is_configured()
```

### Combining Params with IDs

```python
@pytest.fixture(params=[
    pytest.param("sqlite", id="sqlite-inmemory"),
    pytest.param("postgres", id="postgres-docker"),
])
def database_type(request):
    return request.param
```

## Scope Pattern Variations

### Reusing Logic Across Scopes

```python
from contextlib import contextmanager

@contextmanager
def _database_connection():
    conn = create_connection()
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def db_per_test():
    with _database_connection() as conn:
        yield conn


@pytest.fixture(scope="module")
def db_per_module():
    with _database_connection() as conn:
        yield conn
```

### Scoped Factory

```python
@pytest.fixture(scope="module")
def user_factory(database):
    """Module-scoped factory - users persist across tests in module."""
    def _create(**kwargs):
        return User.create(database, **kwargs)
    return _create
```

## Request Object Patterns

### Accessing Test Metadata

```python
@pytest.fixture
def resource(request):
    name = f"resource_{request.node.name}"
    markers = list(request.node.iter_markers())

    resource = Resource(name=name)

    if request.node.get_closest_marker("slow"):
        resource.configure_for_slow_test()

    return resource
```

### Dynamic Fixture Selection

```python
@pytest.fixture
def env_config(request):
    env = request.config.getoption("--env", default="test")
    return load_config(env)
```

### Multiple Finalizers

```python
@pytest.fixture
def managed_resources(request):
    resources = []

    def add(resource):
        resources.append(resource)
        request.addfinalizer(resource.cleanup)
        return resource

    return add
```

## Async Fixture Patterns

Requires `pytest-asyncio`:

```python
import pytest_asyncio

@pytest_asyncio.fixture
async def async_client():
    client = AsyncClient()
    await client.connect()
    yield client
    await client.disconnect()


@pytest_asyncio.fixture(scope="session")
async def database_pool():
    pool = await create_pool(min_size=5, max_size=20)
    yield pool
    await pool.close()
```

## Database Transaction Patterns

### Rollback After Each Test

```python
@pytest.fixture
def db_session(database):
    connection = database.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()
```

### Nested Transactions (Savepoints)

```python
@pytest.fixture
def nested_transaction(db_session):
    savepoint = db_session.begin_nested()
    yield db_session
    savepoint.rollback()
```

## Mock Integration Patterns

### Mock with Spec

```python
@pytest.fixture
def mock_api_client():
    mock = Mock(spec=APIClient)
    mock.get.return_value = {"status": "ok"}
    return mock
```

### Patch as Fixture

```python
@pytest.fixture
def patched_datetime():
    with patch("mymodule.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2024, 1, 1, 12, 0, 0)
        yield mock_dt
```

### Responses/HTTPX Mock

```python
@pytest.fixture
def mock_external_api():
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            "https://api.example.com/users",
            json={"users": []},
            status=200,
        )
        yield rsps
```

## Temporary File Patterns

### Using tmp_path

```python
@pytest.fixture
def config_file(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("debug: true\nlog_level: INFO")
    return config
```

### Temp Directory with Structure

```python
@pytest.fixture
def project_directory(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "__init__.py").touch()
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
    return tmp_path
```

## Environment Variable Patterns

### Using monkeypatch

```python
@pytest.fixture
def test_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.delenv("PRODUCTION_KEY", raising=False)
```

### Environment Context Manager

```python
@pytest.fixture
def isolated_env(monkeypatch):
    """Clear and set minimal environment."""
    for key in list(os.environ.keys()):
        if key.startswith("MY_APP_"):
            monkeypatch.delenv(key)

    monkeypatch.setenv("MY_APP_ENV", "test")
    yield
```

## Logging/Output Capture Patterns

### Capturing Logs

```python
def test_logs_warning(caplog):
    with caplog.at_level(logging.WARNING):
        my_function()

    assert "expected warning" in caplog.text
    assert len(caplog.records) == 1
```

### Capturing stdout/stderr

```python
def test_prints_output(capsys):
    print("hello")
    captured = capsys.readouterr()
    assert captured.out == "hello\n"
    assert captured.err == ""
```

## Class-Based Test Organization

### Using Class Scope

```python
@pytest.fixture(scope="class")
def shared_resource(request):
    resource = ExpensiveResource()
    request.cls.resource = resource  # Attach to class
    yield resource
    resource.cleanup()


class TestFeature:
    def test_one(self, shared_resource):
        assert self.resource is shared_resource

    def test_two(self, shared_resource):
        assert self.resource is shared_resource  # Same instance
```

## Plugin-Provided Fixtures

### pytest-django

```python
@pytest.fixture
def user(db):  # db fixture enables database access
    return User.objects.create(username="testuser")


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()
```

### pytest-flask

```python
@pytest.fixture
def app():
    from myapp import create_app
    return create_app(config="testing")


@pytest.fixture
def client(app):
    return app.test_client()
```

### pytest-httpx

```python
@pytest.fixture
def mock_httpx(httpx_mock):
    httpx_mock.add_response(
        url="https://api.example.com/data",
        json={"result": "mocked"},
    )
    return httpx_mock
```
