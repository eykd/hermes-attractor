# Django Acceptance Testing Guide

Django-specific patterns and configurations for acceptance tests with pytest-django.

**Note:** This guide covers the **HTTP Client approach** (pytest + Django test client). For the **BDD approach** (pytest-bdd + Gherkin), see:
- **[gherkin-patterns.md](gherkin-patterns.md)**: Gherkin scenario patterns
- **[step-patterns.md](step-patterns.md)**: Step definition patterns
- **[complete-examples.md](complete-examples.md)**: Complete BDD examples
- **[manual-setup.md](manual-setup.md)**: BDD infrastructure setup
- **[debugging.md](debugging.md)**: BDD debugging guide

## Required Setup

### pytest.ini / pyproject.toml

```ini
[pytest]
DJANGO_SETTINGS_MODULE = myproject.settings.test
python_files = test_*.py
python_functions = test_*
markers =
    acceptance: marks acceptance tests (deselect with '-m "not acceptance"')
    slow: marks slow tests
```

### Test Settings

```python
# myproject/settings/test.py
from .base import *

DEBUG = False
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Speed optimizations
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Disable unnecessary middleware for tests
MIDDLEWARE = [m for m in MIDDLEWARE if 'debug' not in m.lower()]
```

## Essential Fixtures

### conftest.py (Root)

```python
# tests/conftest.py
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user_factory(db):
    """Factory for creating test users."""
    def _create(
        email="testuser@example.com",
        password="TestPass123!",
        is_staff=False,
        is_superuser=False,
        **kwargs
    ):
        return User.objects.create_user(
            email=email,
            password=password,
            is_staff=is_staff,
            is_superuser=is_superuser,
            **kwargs
        )
    return _create


@pytest.fixture
def admin_factory(user_factory):
    """Factory for creating admin users."""
    def _create(**kwargs):
        return user_factory(is_staff=True, is_superuser=True, **kwargs)
    return _create
```

### conftest.py (Acceptance)

```python
# tests/acceptance/conftest.py
import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def logged_in_client(client, user_factory):
    """Client with authenticated regular user."""
    user = user_factory()
    client.force_login(user)
    client.user = user
    return client


@pytest.fixture
def admin_client(client, admin_factory):
    """Client with authenticated admin user."""
    admin = admin_factory(email="admin@example.com")
    client.force_login(admin)
    client.user = admin
    return client


@pytest.fixture
def mailoutbox(settings):
    """Capture sent emails."""
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    from django.core import mail
    mail.outbox.clear()
    return mail.outbox
```

## Django Test Client Patterns

### Basic Requests

```python
def test_get_request(client):
    response = client.get(reverse("home"))
    assert response.status_code == 200

def test_post_request(client):
    response = client.post(reverse("register"), data={
        "email": "new@example.com",
        "password1": "SecurePass123!",
        "password2": "SecurePass123!",
    })
    assert response.status_code == 302

def test_with_query_params(client):
    response = client.get(reverse("search"), {"q": "laptop", "page": 2})
    assert response.status_code == 200
```

### JSON API Requests

```python
def test_json_post(logged_in_client):
    response = logged_in_client.post(
        reverse("api:items"),
        data={"name": "New Item"},
        content_type="application/json"
    )
    assert response.status_code == 201
    assert response.json()["name"] == "New Item"

def test_json_get(logged_in_client):
    response = logged_in_client.get(
        reverse("api:items"),
        HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

### File Uploads

```python
from django.core.files.uploadedfile import SimpleUploadedFile

def test_file_upload(logged_in_client):
    file = SimpleUploadedFile(
        "document.pdf",
        b"PDF content here",
        content_type="application/pdf"
    )
    response = logged_in_client.post(
        reverse("documents:upload"),
        data={"file": file},
        format="multipart"
    )
    assert response.status_code == 201
```

### Following Redirects

```python
def test_redirect_chain(client):
    response = client.post(
        reverse("login"),
        data={"email": "user@example.com", "password": "pass"},
        follow=True  # Follow redirects
    )
    assert response.status_code == 200
    assert response.redirect_chain == [("/dashboard/", 302)]
```

## Assertion Patterns

### Response Content

```python
def test_content_assertions(client, product_factory):
    product = product_factory(name="Widget", price=29.99)
    response = client.get(reverse("products:detail", args=[product.id]))

    content = response.content.decode()

    # Check for text presence
    assert "Widget" in content
    assert "$29.99" in content

    # Check for absence
    assert "Out of Stock" not in content
```

### Template Used

```python
def test_correct_template(client):
    response = client.get(reverse("home"))

    assert response.templates[0].name == "pages/home.html"
    # Or with assertTemplateUsed in pytest-django
    assert "pages/home.html" in [t.name for t in response.templates]
```

### Context Variables

```python
def test_context_variables(client, product_factory):
    products = [product_factory() for _ in range(3)]
    response = client.get(reverse("products:list"))

    # Note: Only check context when it's part of the user contract
    assert "products" in response.context
    assert len(response.context["products"]) == 3
```

### Database State

```python
def test_database_state(logged_in_client, product_factory):
    product = product_factory()

    response = logged_in_client.post(
        reverse("cart:add"),
        data={"product_id": product.id, "quantity": 2}
    )

    # Check database state
    from myapp.models import CartItem
    cart_item = CartItem.objects.get(user=logged_in_client.user)
    assert cart_item.product == product
    assert cart_item.quantity == 2
```

### Messages Framework

```python
from django.contrib.messages import get_messages

def test_success_message(logged_in_client):
    response = logged_in_client.post(
        reverse("profile:update"),
        data={"name": "New Name"}
    )

    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 1
    assert "successfully" in str(messages[0]).lower()
    assert messages[0].level_tag == "success"
```

### Form Errors

```python
def test_form_validation_error(client):
    response = client.post(reverse("register"), data={
        "email": "invalid-email",
        "password1": "short",
        "password2": "different",
    })

    assert response.status_code == 200  # Re-renders form

    # Check form errors in context
    form = response.context["form"]
    assert "email" in form.errors
    assert "password2" in form.errors  # Password mismatch
```

## Common Fixtures

### Product/E-commerce

```python
@pytest.fixture
def product_factory(db):
    from myapp.models import Product

    def _create(
        name="Test Product",
        price=10.00,
        stock=100,
        **kwargs
    ):
        return Product.objects.create(
            name=name,
            price=price,
            stock=stock,
            **kwargs
        )
    return _create


@pytest.fixture
def cart_with_items(logged_in_client, product_factory):
    """Cart pre-populated with items."""
    from myapp.models import Cart, CartItem

    cart = Cart.objects.create(user=logged_in_client.user)
    products = [
        product_factory(name="Item 1", price=25.00),
        product_factory(name="Item 2", price=35.00),
    ]
    for product in products:
        CartItem.objects.create(cart=cart, product=product, quantity=1)

    return {"cart": cart, "products": products, "total": 60.00}
```

### Time Control

```python
import pytest
from freezegun import freeze_time


@pytest.fixture
def frozen_time():
    """Freeze time for deterministic tests."""
    with freeze_time("2024-06-15 12:00:00") as frozen:
        yield frozen


def test_time_sensitive_feature(client, frozen_time):
    # Time is frozen at 2024-06-15 12:00:00
    response = client.get(reverse("time-display"))
    assert "June 15, 2024" in response.content.decode()
```

### External Service Stubs

```python
import responses


@pytest.fixture
def stubbed_payment_api():
    """Stub Stripe API."""
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://api.stripe.com/v1/charges",
            json={
                "id": "ch_test_123",
                "status": "succeeded",
                "amount": 1000,
            },
            status=200
        )
        rsps.add(
            responses.POST,
            "https://api.stripe.com/v1/refunds",
            json={"id": "re_test_456", "status": "succeeded"},
            status=200
        )
        yield rsps


def test_checkout_with_payment(logged_in_client, cart_with_items, stubbed_payment_api):
    response = logged_in_client.post(reverse("checkout"), data={
        "payment_token": "tok_test"
    })
    assert response.status_code == 302
    assert stubbed_payment_api.assert_call_count("https://api.stripe.com/v1/charges", 1)
```

## Running Tests

### Basic Commands

```bash
# Run all acceptance tests
pytest tests/acceptance/

# Run with marker
pytest -m acceptance

# Verbose output
pytest tests/acceptance/ -v

# Stop on first failure
pytest tests/acceptance/ -x

# Run specific test
pytest tests/acceptance/test_checkout_acceptance.py::test_user_can_checkout

# Parallel execution
pytest tests/acceptance/ -n auto
```

### Database Options

```bash
# Reuse database between runs (faster)
pytest --reuse-db

# Create fresh database
pytest --create-db

# Keep database after failure for debugging
pytest --keepdb
```

## Debugging Tips

### Print Response Content

```python
def test_debugging(client):
    response = client.get(reverse("home"))

    # Print full response
    print(response.content.decode())

    # Print status and headers
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")

    # Print redirect chain
    if hasattr(response, 'redirect_chain'):
        print(f"Redirects: {response.redirect_chain}")
```

### Use pytest --pdb

```bash
# Drop into debugger on failure
pytest tests/acceptance/test_checkout.py --pdb
```

### Check SQL Queries

```python
from django.test.utils import CaptureQueriesContext
from django.db import connection

def test_query_count(client, product_factory):
    [product_factory() for _ in range(10)]

    with CaptureQueriesContext(connection) as context:
        response = client.get(reverse("products:list"))

    # Assert reasonable query count (avoid N+1)
    assert len(context) < 5, f"Too many queries: {len(context)}"
```
