# Django Testing with Pytest

Guidelines for testing Django applications using pytest and pytest-django.

## The Three Layers in Django

| Layer | DB Access | Entry Point | What to Test |
|-------|-----------|-------------|--------------|
| **Unit** | No `django_db` | Direct function/method call | Services, domain logic, forms, utilities |
| **Integration** | `django_db` required | Repository/adapter methods | ORM queries, model methods with queries |
| **Acceptance** | `django_db` required | `client` fixture (HTTP) | Full request/response cycle |

## Unit Tests (No Database)

Unit tests should **not** use `@pytest.mark.django_db`. If a test requires this marker, consider:
1. Refactoring the code to separate logic from persistence
2. Moving the test to integration tests

### Testing Services

```python
# tests/unit/test_checkout_service.py
from myapp.services import CheckoutService


class TestCheckoutService:
    def test_applies_loyalty_discount(self, mocker):
        # Mock the repository (don't hit DB)
        repo = mocker.Mock()
        repo.get_discount_rate.return_value = 0.10

        service = CheckoutService(repository=repo)

        total = service.calculate_total(subtotal=100, customer_id=1)

        assert total == 90
        repo.get_discount_rate.assert_called_once_with(customer_id=1)

    def test_rejects_empty_cart(self):
        service = CheckoutService()

        with pytest.raises(EmptyCartError):
            service.calculate_total(subtotal=0, customer_id=1)
```

### Testing Forms (Validation Logic)

```python
# tests/unit/test_forms.py
from myapp.forms import RegistrationForm


class TestRegistrationForm:
    def test_rejects_mismatched_passwords(self):
        form = RegistrationForm(data={
            "email": "test@example.com",
            "password1": "secretpass123",
            "password2": "differentpass456",
        })

        assert not form.is_valid()
        assert "password2" in form.errors

    def test_rejects_invalid_email(self):
        form = RegistrationForm(data={
            "email": "not-an-email",
            "password1": "secretpass123",
            "password2": "secretpass123",
        })

        assert not form.is_valid()
        assert "email" in form.errors
```

### Testing Model Methods (Pure Logic Only)

```python
# tests/unit/test_models.py
from myapp.models import Order


class TestOrderModel:
    def test_full_name_combines_first_and_last(self):
        # Instantiate without saving - no DB needed
        user = User(first_name="Alice", last_name="Smith")

        assert user.full_name == "Alice Smith"

    def test_order_is_overdue_after_30_days(self):
        order = Order(
            created_at=datetime(2024, 1, 1),
            status="pending"
        )

        # Inject "current" time
        assert order.is_overdue(as_of=datetime(2024, 2, 15))
```

## Integration Tests (With Database)

Use `pytest.mark.django_db` for tests that need real ORM operations.

### File-Level Marker

```python
# tests/integration/test_user_repository.py
import pytest

pytestmark = pytest.mark.django_db  # Applies to all tests in file


class TestUserRepository:
    def test_saves_and_retrieves_user(self, user_factory):
        user = user_factory(email="alice@example.com")

        loaded = User.objects.get(email="alice@example.com")

        assert loaded.pk == user.pk
        assert loaded.email == "alice@example.com"
```

### Testing Model Methods with Queries

```python
# tests/integration/test_order_model.py
import pytest

pytestmark = pytest.mark.django_db


class TestOrderQueryMethods:
    def test_get_recent_returns_last_30_days(self, order_factory):
        old_order = order_factory(created_at=datetime(2024, 1, 1))
        recent_order = order_factory(created_at=datetime(2024, 2, 10))

        # Method that performs a query
        recent = Order.get_recent(as_of=datetime(2024, 2, 15))

        assert recent_order in recent
        assert old_order not in recent
```

### Testing Custom QuerySets/Managers

```python
# tests/integration/test_managers.py
import pytest

pytestmark = pytest.mark.django_db


class TestOrderManager:
    def test_pending_excludes_completed_orders(self, order_factory):
        pending = order_factory(status="pending")
        completed = order_factory(status="completed")

        result = Order.objects.pending()

        assert pending in result
        assert completed not in result
```

## Acceptance Tests (HTTP Layer)

Test complete features through the HTTP interface.

### Basic Pattern

```python
# tests/acceptance/test_user_registration.py
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestUserRegistration:
    def test_user_can_register_with_valid_data(self, client):
        url = reverse("register")

        response = client.post(url, {
            "email": "newuser@example.com",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })

        # Redirects to success page
        assert response.status_code == 302
        assert response["Location"] == reverse("registration_complete")

        # User exists in database
        assert User.objects.filter(email="newuser@example.com").exists()

    def test_registration_fails_with_existing_email(self, client, user_factory):
        existing = user_factory(email="taken@example.com")
        url = reverse("register")

        response = client.post(url, {
            "email": "taken@example.com",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })

        assert response.status_code == 200  # Re-renders form
        assert b"already exists" in response.content
```

### Testing Authenticated Views

```python
class TestDashboard:
    def test_redirects_anonymous_user_to_login(self, client):
        url = reverse("dashboard")

        response = client.get(url)

        assert response.status_code == 302
        assert "login" in response["Location"]

    def test_shows_dashboard_for_authenticated_user(self, client, user_factory):
        user = user_factory()
        client.force_login(user)

        response = client.get(reverse("dashboard"))

        assert response.status_code == 200
        assert b"Welcome" in response.content
```

### Testing API Views (DRF)

```python
# tests/acceptance/test_api.py
import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestOrderAPI:
    def test_list_orders_for_authenticated_user(self, api_client, user_factory, order_factory):
        user = user_factory()
        order = order_factory(user=user)
        other_order = order_factory()  # Different user

        api_client.force_authenticate(user=user)
        response = api_client.get("/api/orders/")

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == order.id

    def test_create_order_returns_201(self, api_client, user_factory, product_factory):
        user = user_factory()
        product = product_factory()
        api_client.force_authenticate(user=user)

        response = api_client.post("/api/orders/", {
            "product_id": product.id,
            "quantity": 2,
        })

        assert response.status_code == 201
        assert Order.objects.filter(user=user).exists()
```

## Factory Fixtures

Use factories for creating test data consistently.

```python
# tests/conftest.py
import pytest
from myapp.models import User, Order, Product


@pytest.fixture
def user_factory(db):
    def _create_user(
        email="test@example.com",
        password="testpass123",
        **kwargs
    ):
        return User.objects.create_user(
            email=email,
            password=password,
            **kwargs
        )
    return _create_user


@pytest.fixture
def order_factory(db, user_factory):
    def _create_order(user=None, status="pending", **kwargs):
        if user is None:
            user = user_factory()
        return Order.objects.create(user=user, status=status, **kwargs)
    return _create_order
```

### Using factory_boy (Optional)

```python
# tests/factories.py
import factory
from myapp.models import User, Order


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    user = factory.SubFactory(UserFactory)
    status = "pending"


# In tests:
def test_order_creation(db):
    order = OrderFactory(status="completed")
    assert order.status == "completed"
```

## What NOT to Do in Django Tests

### Don't Mock the ORM in Integration Tests

```python
# BAD: Mocking what you're trying to test
def test_user_repository(mocker):
    mocker.patch.object(User.objects, "get")  # Defeats the purpose!

# GOOD: Use real ORM
@pytest.mark.django_db
def test_user_repository():
    User.objects.create(email="test@example.com")
    user = User.objects.get(email="test@example.com")
    assert user.email == "test@example.com"
```

### Don't Use `django_db` for Pure Logic

```python
# BAD: Unnecessary database access
@pytest.mark.django_db
def test_email_validation():
    form = EmailForm(data={"email": "invalid"})
    assert not form.is_valid()

# GOOD: No marker needed
def test_email_validation():
    form = EmailForm(data={"email": "invalid"})
    assert not form.is_valid()
```

### Don't Test Django Internals

```python
# BAD: Testing Django's auth system
def test_user_password_is_hashed(user_factory):
    user = user_factory(password="secret")
    assert user.password != "secret"  # Django does this

# GOOD: Test YOUR code's behavior
def test_user_can_authenticate(client, user_factory):
    user = user_factory(password="secret")
    assert client.login(email=user.email, password="secret")
```

### Don't Call Views Directly in Acceptance Tests

```python
# BAD: Bypasses URL routing, middleware
def test_dashboard(user_factory):
    user = user_factory()
    request = RequestFactory().get("/dashboard/")
    request.user = user
    response = dashboard_view(request)  # Direct call

# GOOD: Use the client
def test_dashboard(client, user_factory):
    user = user_factory()
    client.force_login(user)
    response = client.get(reverse("dashboard"))
```

## Django Settings for Testing

```python
# settings/test.py or pytest configuration

# Faster password hashing for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# In-memory email backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Faster database (if not using transactions)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
```

## Checklist: Is This Test in the Right Layer?

| If the test... | It belongs in... |
|----------------|------------------|
| Calls `client.get()` or `client.post()` | Acceptance |
| Uses `@pytest.mark.django_db` | Integration or Acceptance |
| Tests a queryset or manager method | Integration |
| Tests form validation without DB | Unit |
| Tests a service with mocked repository | Unit |
| Tests URL routing and redirects | Acceptance |
| Tests a model's computed property | Unit |
| Tests a model's save() with side effects | Integration |
