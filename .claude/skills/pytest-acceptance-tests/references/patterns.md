# Acceptance Test Patterns

Detailed patterns and examples for writing effective acceptance tests.

## Pattern 1: Complete User Journey Test

Tests a full user workflow from start to finish.

```python
def test_new_user_registration_to_first_purchase(client, product_factory):
    """Complete journey: register → browse → add to cart → checkout."""
    product = product_factory(name="Widget", price=50.00)

    # Register
    response = client.post(reverse("register"), data={
        "email": "newuser@example.com",
        "password1": "SecurePass123!",
        "password2": "SecurePass123!",
    })
    assert response.status_code == 302

    # Add to cart (now logged in via registration)
    response = client.post(reverse("cart:add"), data={"product_id": product.id})
    assert response.status_code == 302

    # Complete checkout
    response = client.post(reverse("checkout"), data={
        "shipping_address": "123 Main St, City, ST 12345",
    })
    assert response.status_code == 302
    assert Order.objects.filter(user__email="newuser@example.com").exists()
```

## Pattern 2: Error Path Test

Tests that error conditions produce appropriate user feedback.

```python
def test_registration_with_existing_email_shows_error(client, user_factory):
    """Attempting to register with taken email shows helpful message."""
    existing_user = user_factory(email="taken@example.com")

    response = client.post(reverse("register"), data={
        "email": "taken@example.com",
        "password1": "SecurePass123!",
        "password2": "SecurePass123!",
    })

    assert response.status_code == 200  # Re-renders form
    content = response.content.decode()
    assert "email" in content.lower()
    assert "already" in content.lower() or "exists" in content.lower()
```

## Pattern 3: Authorization Test

Tests access control from user perspective.

```python
def test_guest_cannot_access_admin_dashboard(client):
    """Unauthenticated users are redirected to login."""
    response = client.get(reverse("admin:dashboard"))

    assert response.status_code == 302
    assert "login" in response["Location"].lower()


def test_regular_user_cannot_access_admin_dashboard(logged_in_client):
    """Non-admin users see forbidden page."""
    response = logged_in_client.get(reverse("admin:dashboard"))

    assert response.status_code == 403


def test_admin_can_access_admin_dashboard(admin_client):
    """Admin users can view dashboard."""
    response = admin_client.get(reverse("admin:dashboard"))

    assert response.status_code == 200
    assert "Dashboard" in response.content.decode()
```

## Pattern 4: Search and Filter Test

Tests discovery features.

```python
def test_product_search_returns_relevant_results(client, product_factory):
    """Search filters products by name."""
    laptop = product_factory(name="Gaming Laptop", category="Electronics")
    mouse = product_factory(name="Wireless Mouse", category="Electronics")
    book = product_factory(name="Python Cookbook", category="Books")

    response = client.get(reverse("products:search"), {"q": "laptop"})
    content = response.content.decode()

    assert response.status_code == 200
    assert "Gaming Laptop" in content
    assert "Wireless Mouse" not in content
    assert "Python Cookbook" not in content


def test_empty_search_shows_all_products(client, product_factory):
    """Empty query returns complete catalog."""
    product_factory(name="Product A")
    product_factory(name="Product B")

    response = client.get(reverse("products:search"), {"q": ""})
    content = response.content.decode()

    assert "Product A" in content
    assert "Product B" in content
```

## Pattern 5: Form Validation Test

Tests client-facing validation messages.

```python
def test_checkout_requires_shipping_address(logged_in_client, cart_with_items):
    """Missing address shows validation error."""
    response = logged_in_client.post(reverse("checkout"), data={
        "shipping_address": "",  # Missing required field
    })

    assert response.status_code == 200  # Re-renders form
    assert "shipping" in response.content.decode().lower()
    assert "required" in response.content.decode().lower()
```

## Pattern 6: Pagination Test

Tests list navigation.

```python
def test_product_list_paginates_results(client, product_factory):
    """Product list shows paginated results with navigation."""
    for i in range(25):
        product_factory(name=f"Product {i}")

    # First page
    response = client.get(reverse("products:list"))
    content = response.content.decode()
    assert "Product 0" in content
    assert "Product 19" in content
    assert "Product 20" not in content
    assert "Next" in content or "page=2" in content

    # Second page
    response = client.get(reverse("products:list"), {"page": 2})
    content = response.content.decode()
    assert "Product 20" in content
    assert "Product 0" not in content
```

## Pattern 7: AJAX/API Response Test

Tests JSON API endpoints.

```python
def test_cart_api_returns_item_count(logged_in_client, product_factory):
    """Cart API endpoint returns current item count."""
    product = product_factory()
    logged_in_client.post(reverse("cart:add"), data={"product_id": product.id})

    response = logged_in_client.get(
        reverse("cart:status"),
        HTTP_ACCEPT="application/json"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["item_count"] == 1
    assert "total" in data
```

## Pattern 8: File Upload Test

Tests file handling from user perspective.

```python
def test_user_can_upload_profile_picture(logged_in_client):
    """Profile picture upload updates user avatar."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    image = SimpleUploadedFile(
        "avatar.png",
        b"fake-image-content",
        content_type="image/png"
    )

    response = logged_in_client.post(
        reverse("profile:upload-avatar"),
        data={"avatar": image},
        format="multipart"
    )

    assert response.status_code == 302
    logged_in_client.user.refresh_from_db()
    assert logged_in_client.user.avatar is not None
```

## Pattern 9: Email Verification Test

Tests email-triggered workflows (with stubbed email backend).

```python
@pytest.fixture
def mailoutbox(settings):
    """Capture outgoing emails."""
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    from django.core import mail
    return mail.outbox


def test_registration_sends_verification_email(client, mailoutbox):
    """New registration triggers verification email."""
    response = client.post(reverse("register"), data={
        "email": "newuser@example.com",
        "password1": "SecurePass123!",
        "password2": "SecurePass123!",
    })

    assert response.status_code == 302
    assert len(mailoutbox) == 1
    assert "newuser@example.com" in mailoutbox[0].to
    assert "verify" in mailoutbox[0].subject.lower()
```

## Pattern 10: Time-Sensitive Feature Test

Tests features affected by time using freezegun.

```python
from freezegun import freeze_time


@freeze_time("2024-12-25 10:00:00")
def test_holiday_banner_shows_on_christmas(client):
    """Holiday banner appears on December 25."""
    response = client.get(reverse("home"))
    assert "Merry Christmas" in response.content.decode()


@freeze_time("2024-06-15 10:00:00")
def test_holiday_banner_hidden_in_summer(client):
    """Holiday banner does not appear outside holiday season."""
    response = client.get(reverse("home"))
    assert "Merry Christmas" not in response.content.decode()
```

## Pattern 11: Multi-Step Workflow Test

Tests workflows with intermediate states.

```python
def test_password_reset_workflow(client, user_factory, mailoutbox):
    """Complete password reset: request → email → reset → login."""
    user = user_factory(email="user@example.com")

    # Step 1: Request reset
    response = client.post(reverse("password:reset"), data={
        "email": "user@example.com"
    })
    assert response.status_code == 302
    assert len(mailoutbox) == 1

    # Extract token from email (simplified)
    import re
    match = re.search(r'/reset/([^/]+)/([^/]+)/', mailoutbox[0].body)
    uidb64, token = match.groups()

    # Step 2: Access reset page
    response = client.get(reverse("password:reset-confirm", args=[uidb64, token]))
    assert response.status_code == 200

    # Step 3: Set new password
    response = client.post(
        reverse("password:reset-confirm", args=[uidb64, token]),
        data={"new_password1": "NewSecure123!", "new_password2": "NewSecure123!"}
    )
    assert response.status_code == 302

    # Step 4: Login with new password
    response = client.post(reverse("login"), data={
        "email": "user@example.com",
        "password": "NewSecure123!"
    })
    assert response.status_code == 302
```

## Fixture Patterns

### Database Rollback Fixture

```python
@pytest.fixture
def db_session(db):
    """Ensure each test runs in isolated transaction."""
    # pytest-django handles this automatically with @pytest.mark.django_db
    yield
```

### External Service Stub Fixture

```python
@pytest.fixture
def stubbed_payment_gateway():
    """Stub external payment API for acceptance tests."""
    import responses

    responses.start()
    responses.add(
        responses.POST,
        "https://api.stripe.com/v1/charges",
        json={"id": "ch_test", "status": "succeeded"},
        status=200
    )

    yield

    responses.stop()
    responses.reset()
```

### Parameterized Test User Fixture

```python
@pytest.fixture(params=[
    {"role": "viewer", "can_edit": False},
    {"role": "editor", "can_edit": True},
    {"role": "admin", "can_edit": True},
])
def user_with_role(request, user_factory):
    """Generate tests for each user role."""
    user = user_factory(role=request.param["role"])
    user.expected_can_edit = request.param["can_edit"]
    return user
```

## Assertion Helpers

### Content Assertion Helper

```python
def assert_contains_message(response, message_type, text):
    """Assert response contains Django message."""
    from django.contrib.messages import get_messages
    messages = list(get_messages(response.wsgi_request))
    matching = [m for m in messages if m.level_tag == message_type and text in str(m)]
    assert matching, f"No {message_type} message containing '{text}'"


# Usage
def test_successful_save_shows_message(logged_in_client):
    response = logged_in_client.post(reverse("profile:save"), data={...})
    assert_contains_message(response, "success", "saved")
```

### Form Error Assertion Helper

```python
def assert_form_error(response, field, error_text):
    """Assert form has specific field error."""
    assert response.context is not None, "No context in response"
    form = response.context.get("form")
    assert form is not None, "No form in context"
    assert field in form.errors, f"No errors for field '{field}'"
    errors = " ".join(form.errors[field])
    assert error_text.lower() in errors.lower(), f"'{error_text}' not in '{errors}'"
```
