# Django Fixtures Reference (pytest-django)

Patterns and best practices for pytest fixtures in Django projects.

## Setup

Install pytest-django:
```bash
uv add --group=test pytest-django
```

Configure in `pytest.ini` or `pyproject.toml`:
```ini
# pytest.ini
[pytest]
DJANGO_SETTINGS_MODULE = myproject.settings.test
python_files = test_*.py
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "myproject.settings.test"
python_files = ["test_*.py"]
```

## Database Access

### The `db` Fixture

Tests need explicit database access. Use `@pytest.mark.django_db` or request the `db` fixture:

```python
import pytest

@pytest.mark.django_db
def test_user_creation():
    user = User.objects.create(username="alice")
    assert User.objects.count() == 1


# Or via fixture dependency
def test_user_query(db):
    User.objects.create(username="bob")
    assert User.objects.filter(username="bob").exists()
```

### Transaction Behavior

By default, each test runs in a transaction that rolls back. For tests needing real commits:

```python
@pytest.mark.django_db(transaction=True)
def test_with_real_transactions():
    # Transactions actually commit
    pass
```

### Database Fixtures with Cleanup

```python
@pytest.fixture
def user(db):
    """Creates a user, auto-cleaned by transaction rollback."""
    return User.objects.create(
        username="testuser",
        email="test@example.com"
    )


@pytest.fixture
def users(db):
    """Creates multiple users."""
    return [
        User.objects.create(username=f"user_{i}")
        for i in range(3)
    ]
```

## Model Fixtures

### Basic Model Fixture

```python
@pytest.fixture
def category(db):
    return Category.objects.create(name="Electronics", slug="electronics")


@pytest.fixture
def product(db, category):
    return Product.objects.create(
        name="Laptop",
        category=category,
        price=999.99
    )
```

### Factory Fixture for Models

```python
@pytest.fixture
def create_user(db):
    """Factory for creating users with custom attributes."""
    def _create_user(
        username=None,
        email=None,
        password="testpass123",
        **kwargs
    ):
        if username is None:
            username = f"user_{User.objects.count()}"
        if email is None:
            email = f"{username}@test.com"

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            **kwargs
        )
        return user

    return _create_user


def test_user_permissions(create_user):
    admin = create_user(username="admin", is_staff=True)
    regular = create_user(username="regular")

    assert admin.is_staff
    assert not regular.is_staff
```

### Using Factory Boy (Recommended for Complex Models)

```python
# factories.py
import factory
from factory.django import DjangoModelFactory
from myapp.models import User, Order, Product


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@test.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Faker("product_name")
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)


class OrderFactory(DjangoModelFactory):
    class Meta:
        model = Order

    user = factory.SubFactory(UserFactory)
    status = "pending"


# conftest.py
@pytest.fixture
def user_factory(db):
    return UserFactory


@pytest.fixture
def user(db):
    return UserFactory()


# test_orders.py
def test_order_creation(db):
    order = OrderFactory()
    assert order.user is not None
    assert order.status == "pending"
```

## Authentication Fixtures

### Authenticated User

```python
@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )


@pytest.fixture
def authenticated_client(client, user):
    """Django test client logged in as user."""
    client.force_login(user)
    return client


def test_protected_view(authenticated_client):
    response = authenticated_client.get("/dashboard/")
    assert response.status_code == 200
```

### Admin User

```python
@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="adminpass123"
    )


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


def test_admin_panel(admin_client):
    response = admin_client.get("/admin/")
    assert response.status_code == 200
```

### User with Specific Permissions

```python
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


@pytest.fixture
def user_with_permissions(db, create_user):
    def _create(permissions):
        user = create_user()
        for perm in permissions:
            app_label, codename = perm.split(".")
            permission = Permission.objects.get(
                content_type__app_label=app_label,
                codename=codename
            )
            user.user_permissions.add(permission)
        return user
    return _create


def test_editor_access(user_with_permissions, client):
    editor = user_with_permissions(["blog.change_post", "blog.add_post"])
    client.force_login(editor)
    # Test editor capabilities
```

## Client Fixtures

### Standard Test Client

pytest-django provides `client` automatically:

```python
def test_homepage(client):
    response = client.get("/")
    assert response.status_code == 200
```

### API Client (Django REST Framework)

```python
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_api_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


def test_api_list(authenticated_api_client):
    response = authenticated_api_client.get("/api/items/")
    assert response.status_code == 200
```

### Client with Specific Headers

```python
@pytest.fixture
def json_client(client):
    """Client that sends JSON by default."""
    original_post = client.post
    original_put = client.put
    original_patch = client.patch

    def json_post(path, data=None, **kwargs):
        kwargs.setdefault("content_type", "application/json")
        return original_post(path, data, **kwargs)

    client.post = json_post
    # Similar for put, patch...
    return client
```

## Request Factory Fixtures

For testing views without full HTTP stack:

```python
from django.test import RequestFactory


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.fixture
def get_request(request_factory, user):
    request = request_factory.get("/fake-path/")
    request.user = user
    return request


def test_view_directly(get_request):
    from myapp.views import my_view
    response = my_view(get_request)
    assert response.status_code == 200
```

## Settings Fixtures

### Override Settings

```python
@pytest.fixture
def debug_settings(settings):
    settings.DEBUG = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    return settings


def test_with_debug(debug_settings):
    from django.conf import settings
    assert settings.DEBUG is True
```

### Temporary Setting Override

```python
from django.test import override_settings


@pytest.fixture
def stripe_test_mode():
    with override_settings(STRIPE_LIVE_MODE=False, STRIPE_SECRET_KEY="sk_test_xxx"):
        yield


def test_payment(stripe_test_mode):
    # Uses test Stripe settings
    pass
```

## Cache and Session Fixtures

### Clear Cache

```python
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    yield
    cache.clear()


# Or per-test
@pytest.fixture
def empty_cache():
    cache.clear()
    yield
    cache.clear()
```

### Session Data

```python
@pytest.fixture
def session_with_cart(client):
    session = client.session
    session["cart"] = {"items": [], "total": 0}
    session.save()
    return client
```

## Mail Fixtures

```python
from django.core import mail


@pytest.fixture
def mailbox():
    """Access sent emails. Requires locmem email backend."""
    mail.outbox.clear()
    yield mail.outbox
    mail.outbox.clear()


def test_sends_welcome_email(mailbox, create_user):
    create_user(email="new@example.com")

    assert len(mailbox) == 1
    assert mailbox[0].to == ["new@example.com"]
    assert "Welcome" in mailbox[0].subject
```

## File Upload Fixtures

```python
from django.core.files.uploadedfile import SimpleUploadedFile


@pytest.fixture
def image_file():
    """Create a simple test image."""
    return SimpleUploadedFile(
        name="test_image.jpg",
        content=b"\x47\x49\x46\x38\x89\x61",  # GIF header bytes
        content_type="image/jpeg"
    )


@pytest.fixture
def csv_file():
    content = b"name,email\nAlice,alice@test.com\nBob,bob@test.com"
    return SimpleUploadedFile(
        name="data.csv",
        content=content,
        content_type="text/csv"
    )


def test_file_upload(authenticated_client, image_file):
    response = authenticated_client.post(
        "/upload/",
        {"file": image_file},
        format="multipart"
    )
    assert response.status_code == 201
```

## Async Fixtures (Django 4.1+)

```python
import pytest
from asgiref.sync import sync_to_async


@pytest.fixture
async def async_user(db):
    @sync_to_async
    def create():
        return User.objects.create_user(username="async_user")
    return await create()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_async_view(async_client, async_user):
    response = await async_client.get("/async-endpoint/")
    assert response.status_code == 200
```

## Celery Task Fixtures

```python
@pytest.fixture
def celery_eager(settings):
    """Execute Celery tasks synchronously."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


def test_async_task(celery_eager):
    from myapp.tasks import send_notification
    result = send_notification.delay(user_id=1)
    assert result.successful()
```

## Fixture Organization for Django Projects

### Recommended conftest.py Structure

```
tests/
├── conftest.py                 # Shared fixtures
│   ├── user fixtures
│   ├── client fixtures
│   └── factory imports
├── unit/
│   ├── conftest.py             # Unit-specific (mocks)
│   └── test_models.py
├── integration/
│   ├── conftest.py             # DB fixtures
│   └── test_views.py
└── e2e/
    ├── conftest.py             # Full stack fixtures
    └── test_flows.py
```

### Root conftest.py Example

```python
# tests/conftest.py
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


# ============ User Fixtures ============

@pytest.fixture
def create_user(db):
    """Factory for creating users."""
    def _create(username=None, email=None, password="pass123", **kwargs):
        username = username or f"user_{User.objects.count()}"
        email = email or f"{username}@test.com"
        return User.objects.create_user(username, email, password, **kwargs)
    return _create


@pytest.fixture
def user(create_user):
    return create_user()


@pytest.fixture
def admin_user(create_user):
    return create_user(username="admin", is_staff=True, is_superuser=True)


# ============ Client Fixtures ============

@pytest.fixture
def authenticated_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


# ============ API Fixtures (if using DRF) ============

@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_api_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client
```

## Common Patterns

### Testing Model Methods

```python
@pytest.fixture
def order_with_items(db, create_user):
    user = create_user()
    order = Order.objects.create(user=user, status="pending")
    OrderItem.objects.create(order=order, product_name="Widget", price=10, qty=2)
    OrderItem.objects.create(order=order, product_name="Gadget", price=25, qty=1)
    return order


def test_order_total(order_with_items):
    assert order_with_items.total == 45  # (10*2) + (25*1)
```

### Testing Form Validation

```python
@pytest.fixture
def valid_registration_data():
    return {
        "username": "newuser",
        "email": "new@example.com",
        "password1": "securepass123",
        "password2": "securepass123",
    }


def test_registration_form(db, valid_registration_data):
    from myapp.forms import RegistrationForm
    form = RegistrationForm(data=valid_registration_data)
    assert form.is_valid()
```

### Testing Signals

```python
from unittest.mock import patch


@pytest.fixture
def mock_signal_handler():
    with patch("myapp.signals.handle_user_created") as mock:
        yield mock


def test_user_created_signal(db, mock_signal_handler):
    User.objects.create_user("signaltest", "sig@test.com", "pass")
    mock_signal_handler.assert_called_once()
```
