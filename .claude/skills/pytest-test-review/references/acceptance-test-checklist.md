# Acceptance Test Review Checklist

Detailed checklist for reviewing pytest acceptance tests following GOOS principles.

## Purpose
An acceptance test describes **user-visible behavior end-to-end**, defining the contract of the system from the outside and driving architecture emergence.

## Required Criteria

### Structure
- [ ] File under `tests/acceptance/` or clearly organized acceptance location
- [ ] `pytestmark = pytest.mark.django_db` (Django projects)
- [ ] Clear Given–When–Then structure
- [ ] One coherent user story per test
- [ ] Test name describes user scenario

### Interface
- [ ] Uses HTTP layer (`client`) as only entry point
- [ ] Uses `reverse()` for URLs (Django)
- [ ] Hits real URL patterns and routing
- [ ] No direct calls to views, forms, or services

### Scope
- [ ] Tests user-visible behavior
- [ ] Touches real database and templates
- [ ] Exercises full slice: UI → domain → infrastructure
- [ ] Independent of internal implementation details

### Assertions
- [ ] Asserts on status codes
- [ ] Asserts on redirect targets (for redirect flows)
- [ ] Asserts on key user-visible content
- [ ] Asserts on essential database state changes
- [ ] Does NOT assert on exact HTML structure (unless it IS the contract)

## Red Flags

### Critical (Block PR)
- Directly calls view functions or services
- Mocks Django internals (ORM, templates, middleware)
- No database marker when DB is required
- Tests implementation details, not user behavior

### Significant (Request Changes)
- Multiple unrelated user stories in one test
- Asserts on internal context keys
- Missing status code assertions
- Missing database state verification for state-changing operations
- Hardcoded URLs instead of `reverse()`

### Minor (Suggest Improvement)
- Could use more domain-focused language in test name
- Assertion messages could be more helpful
- Heavy fixtures hiding test intent

## Good Example

```python
# tests/acceptance/test_user_registration.py
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_user_can_register_with_valid_credentials(client):
    # Given: the registration page exists
    url = reverse("register")

    # When: user submits valid registration
    response = client.post(url, {
        "email": "alice@example.com",
        "password1": "SecurePass123!",
        "password2": "SecurePass123!",
    })

    # Then: user is redirected to welcome page
    assert response.status_code == 302
    assert response["Location"].endswith(reverse("welcome"))

    # And: user exists in database
    from django.contrib.auth import get_user_model
    User = get_user_model()
    assert User.objects.filter(email="alice@example.com").exists()


def test_registration_fails_with_mismatched_passwords(client):
    # Given: the registration page
    url = reverse("register")

    # When: user submits mismatched passwords
    response = client.post(url, {
        "email": "bob@example.com",
        "password1": "SecurePass123!",
        "password2": "DifferentPass456!",
    })

    # Then: stays on registration page with error
    assert response.status_code == 200
    assert b"passwords" in response.content.lower()

    # And: no user created
    from django.contrib.auth import get_user_model
    User = get_user_model()
    assert not User.objects.filter(email="bob@example.com").exists()
```

**Why it's good:**
- Uses HTTP client as only interface
- Uses `reverse()` for URLs
- Clear Given–When–Then structure
- Tests user-visible outcomes
- Verifies both HTTP response and database state
- Each test is one user story

## Bad Example

```python
def test_registration(db):
    from myapp.views import register_view
    from myapp.forms import RegistrationForm

    form = RegistrationForm(data={
        "email": "test@test.com",
        "password1": "pass",
        "password2": "pass",
    })

    if form.is_valid():
        user = form.save()
        assert user.email == "test@test.com"
        assert user.check_password("pass")

    # Also test the email service
    from myapp.services import EmailService
    service = EmailService()
    assert service.send_welcome_email(user)
```

**Why it's bad:**
- Directly imports and calls view/form
- Doesn't use HTTP client
- Tests implementation (form, service) not user behavior
- Combines multiple concerns
- Password validation probably fails ("pass" too short)
- Test name doesn't describe user scenario

## Assertion Guidance

### Always Assert
- Status code (200, 302, 404, etc.)
- Redirect location for redirect responses
- Key phrases in response content
- Database state changes for mutations

### Sometimes Assert
- Specific error messages (if part of contract)
- Response headers (if part of contract)
- JSON structure for API responses

### Avoid Asserting
- Exact HTML structure
- CSS classes or DOM IDs
- Internal context variables
- Non-essential wording
