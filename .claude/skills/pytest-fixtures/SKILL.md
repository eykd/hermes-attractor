---
name: pytest-fixtures
description: "Use when: (1) Writing test fixtures for setup/teardown, (2) Organizing conftest.py files, (3) Choosing fixture scopes (function/module/session), (4) Creating factory fixtures, (5) Structuring test directories, (6) Questions about fixture design or pytest-django patterns."
---

# Pytest Fixtures Skill

Write fixtures that support isolated, fast, deterministic, composable, and readable tests.

## Core Principle: Fixture Scope Selection

Default to `function` scope. Only broaden when you have evidence that setup cost hurts development flow.

```
Is test isolation critical?
├── Yes → function scope
└── No → Is setup expensive (>100ms)?
    ├── No → function scope
    └── Yes → Do tests modify fixture state?
        ├── Yes → function scope (accept cost)
        └── No → module or session scope
```

### Scope Reference

| Scope | Lifetime | Use When |
|-------|----------|----------|
| `function` | Per test (default) | Mutable state, fast setup, isolation needed |
| `class` | Per test class | Shared context across class methods |
| `module` | Per .py file | Expensive read-only resources |
| `session` | Entire run | Very expensive setup (containers, pools) |

Execution order: `session → module → class → function` (setup); reverse for teardown.

## Essential Patterns

### Pattern 1: Simple Fixture with Teardown

```python
@pytest.fixture
def database_connection():
    conn = create_connection()
    yield conn  # Setup above, teardown below
    conn.close()
```

### Pattern 2: Factory Fixture

Use when tests need multiple instances or custom configurations.

```python
@pytest.fixture
def create_user():
    created = []

    def _create(name="Test", role="viewer"):
        user = User(name=name, role=role)
        created.append(user)
        return user

    yield _create
    for user in created:
        user.delete()


def test_permissions(create_user):
    admin = create_user(role="admin")
    viewer = create_user(role="viewer")
    assert admin.can_delete(viewer)
```

### Pattern 3: Fixture Composition

```python
@pytest.fixture
def database():
    db = Database(":memory:")
    yield db
    db.close()

@pytest.fixture
def repository(database):  # Depends on database fixture
    return UserRepository(database)

@pytest.fixture
def service(repository):  # Depends on repository fixture
    return UserService(repository)
```

### Pattern 4: Parameterized Fixture

```python
@pytest.fixture(params=["sqlite", "postgres"])
def db_type(request):
    return request.param  # Test runs once per param
```

### Pattern 5: Autouse (Use Sparingly)

```python
@pytest.fixture(autouse=True)
def reset_state():
    GlobalState.reset()
    yield
    GlobalState.reset()
```

## conftest.py Organization

### Hierarchy Rules

- Fixtures in `conftest.py` are available to tests in that directory and all subdirectories
- Place fixtures at the narrowest scope where they're needed
- Root `conftest.py`: session-scoped infrastructure
- Category `conftest.py`: test-type-specific fixtures

### Recommended Structure

```
tests/
├── conftest.py              # Shared: app instance, DB pool
├── unit/
│   ├── conftest.py          # Mocks, stubs, lightweight fakes
│   └── test_*.py
├── integration/
│   ├── conftest.py          # Real DB with cleanup
│   └── test_*.py
└── e2e/
    ├── conftest.py          # Browser, full app fixtures
    └── test_*.py
```

## Test Type Guidelines

### Unit Test Fixtures

- No database, network, or filesystem
- Use mocks for external dependencies
- Setup should be <10ms

```python
@pytest.fixture
def mock_repository():
    return Mock(spec=UserRepository)

@pytest.fixture
def service(mock_repository):
    return UserService(repository=mock_repository)
```

### Integration Test Fixtures

- Real database with transaction rollback or cleanup
- Controlled fakes for external APIs

```python
@pytest.fixture
def database():
    db = create_test_database()
    yield db
    db.rollback()  # or db.delete_all()
```

### E2E/Acceptance Fixtures

- Full application instance
- Browser automation, test users

```python
@pytest.fixture(scope="session")
def app():
    return create_app(config="testing")

@pytest.fixture
def authenticated_client(app, create_user):
    user = create_user()
    return app.test_client(user=user)
```

## Built-in Fixtures

| Fixture | Purpose |
|---------|---------|
| `tmp_path` | Temp directory (function scope) |
| `tmp_path_factory` | Temp path factory (session scope) |
| `capsys` | Capture stdout/stderr |
| `caplog` | Capture log messages |
| `monkeypatch` | Modify objects/env temporarily |
| `request` | Access test context |

## Anti-Patterns to Avoid

1. **Missing teardown**: Always use `yield` for resources that need cleanup
2. **Session scope + mutable state**: Causes test pollution
3. **Implicit autouse**: Prefer explicit fixture injection
4. **Deep fixture chains**: Flatten when possible (max 3 levels)
5. **Generic names**: Use `authenticated_user` not `user` or `data`

## Naming Conventions

- State: `empty_cart`, `populated_database`
- Factory: `create_user`, `make_order`
- Resource: `database_connection`, `redis_client`

## Django Quick Reference (pytest-django)

Requires `uv add --group=test pytest-django` and `DJANGO_SETTINGS_MODULE` in pytest config.

### Database Access

```python
@pytest.mark.django_db
def test_model(db):  # Request db fixture or use marker
    User.objects.create(username="test")
```

### Common Django Fixtures

```python
@pytest.fixture
def user(db):
    return User.objects.create_user("test", "test@example.com", "pass")

@pytest.fixture
def authenticated_client(client, user):
    client.force_login(user)
    return client

# For DRF
@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()
```

See [references/django.md](references/django.md) for complete patterns including factories, signals, file uploads, and async support.

## Additional References

For detailed patterns and examples:
- **Fixture patterns**: See [references/patterns.md](references/patterns.md)
- **Test Desiderata mapping**: See [references/desiderata.md](references/desiderata.md)
- **Django fixtures**: See [references/django.md](references/django.md) for pytest-django patterns
