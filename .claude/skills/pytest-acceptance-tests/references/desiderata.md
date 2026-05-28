# Kent Beck's Test Desiderata for Acceptance Tests

How each of the 12 desirable test properties applies specifically to acceptance testing.

## 1. Behavioral Sensitivity

**Principle**: Tests must fail when system behavior changes.

**In Acceptance Tests**: Assert on user-observable outcomes, not implementation details.

```python
# ✅ GOOD: Sensitive to checkout behavior
def test_checkout_creates_order(logged_in_client, cart_with_items):
    response = logged_in_client.post(reverse("checkout"), data={...})

    assert response.status_code == 302
    assert Order.objects.filter(user=logged_in_client.user).exists()

# ❌ BAD: Not sensitive to actual behavior
def test_checkout_page_loads(client):
    response = client.get(reverse("checkout"))
    assert response.status_code == 200  # Doesn't verify checkout works
```

**Verification**: If the feature broke, would this test fail?

## 2. Structure Insensitivity

**Principle**: Tests should survive internal refactoring.

**In Acceptance Tests**: Use HTTP interface only; never call internal methods.

```python
# ✅ GOOD: Structure-insensitive
def test_discount_applied(logged_in_client, cart_with_items):
    logged_in_client.post(reverse("cart:apply-discount"), data={"code": "SAVE10"})
    response = logged_in_client.get(reverse("cart:summary"))
    assert "Discount: -$6.00" in response.content.decode()

# ❌ BAD: Tests internal structure
def test_discount_applied(logged_in_client):
    from myapp.services import DiscountService
    service = DiscountService()
    result = service._apply_discount(cart, "SAVE10")  # Internal method!
```

**Verification**: Could I rename internal classes/methods without breaking this test?

## 3. Readable

**Principle**: Tests should read like self-contained stories.

**In Acceptance Tests**: Use Given-When-Then structure; avoid deep abstractions.

```python
# ✅ GOOD: Reads like a story
def test_user_can_update_shipping_address(logged_in_client):
    """User updates their shipping address successfully."""
    # GIVEN: A logged-in user (provided by fixture)

    # WHEN: User submits new address
    response = logged_in_client.post(reverse("profile:address"), data={
        "street": "456 Oak Ave",
        "city": "Portland",
        "state": "OR",
        "zip": "97201",
    })

    # THEN: Address is updated
    assert response.status_code == 302
    logged_in_client.user.refresh_from_db()
    assert logged_in_client.user.address.street == "456 Oak Ave"

# ❌ BAD: Abstracted beyond comprehension
def test_address_update(client, setup_helper, assertion_helper):
    result = setup_helper.execute_flow("address_update", client)
    assertion_helper.verify(result, "address_scenarios", "success")
```

**Key Insight**: In tests, slight duplication improves clarity. DRY can harm readability.

## 4. Writable

**Principle**: Difficult tests signal design problems.

**In Acceptance Tests**: If setup is massive, the system interface is too coupled.

```python
# ❌ WARNING: Hard to write = design smell
def test_simple_order(
    client, user_factory, product_factory, inventory_factory,
    shipping_factory, tax_config_factory, payment_mock,
    notification_mock, analytics_mock
):
    # 50 lines of setup...
    # Problem is the system, not the test!

# ✅ BETTER: Simple setup indicates good design
def test_simple_order(logged_in_client, cart_with_items):
    response = logged_in_client.post(reverse("checkout"))
    assert response.status_code == 302
```

**Beck's Technique**: Print the test, highlight relevant facts. Too much unhighlighted = interface too broad.

## 5. Fast

**Principle**: Sub-second feedback preserves flow state.

**In Acceptance Tests**: Optimize without sacrificing realism.

```python
# Strategies for fast acceptance tests:

# 1. Use database transactions (pytest-django does this automatically)
@pytest.mark.django_db  # Rolls back after each test

# 2. Session-scoped expensive fixtures
@pytest.fixture(scope="session")
def reference_data(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        load_countries()
        load_currencies()

# 3. Stub slow external services
@pytest.fixture
def stubbed_payment():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.POST, "https://api.stripe.com/...", json={...})
        yield
```

**Target**: Individual acceptance tests < 1 second; full suite < 1 minute.

## 6. Deterministic

**Principle**: Same inputs → same outputs, every time.

**In Acceptance Tests**: Control time, avoid random data.

```python
# ❌ BAD: Non-deterministic
def test_order_timestamp(client):
    client.post(reverse("checkout"))
    order = Order.objects.last()
    assert order.created_at == datetime.now()  # Race condition!

# ✅ GOOD: Deterministic with freezegun
from freezegun import freeze_time

@freeze_time("2024-01-15 12:00:00")
def test_order_timestamp(logged_in_client, cart_with_items):
    logged_in_client.post(reverse("checkout"))
    order = Order.objects.last()
    assert order.created_at == datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

# ❌ BAD: Random data
def test_user_display(client, user_factory):
    user = user_factory(name=faker.name())  # Different every run!

# ✅ GOOD: Fixed data
def test_user_display(client, user_factory):
    user = user_factory(name="Alice Johnson")
```

**Real Example**: Test failed because randomly generated name "Meredith" contained "edit", confusing UI automation clicking "Edit" button.

## 7. Automated

**Principle**: No human intervention required.

**In Acceptance Tests**: Everything verifiable by assertions.

```python
# ❌ BAD: Requires manual verification
def test_email_looks_correct():
    send_welcome_email("test@example.com")
    print("Check your inbox manually")  # Not automated!

# ✅ GOOD: Fully automated
def test_welcome_email_sent(client, mailoutbox):
    client.post(reverse("register"), data={...})

    assert len(mailoutbox) == 1
    assert "welcome" in mailoutbox[0].subject.lower()
    assert "test@example.com" in mailoutbox[0].to
```

## 8. Isolated

**Principle**: Tests must be independent; order cannot matter.

**In Acceptance Tests**: Each test starts with clean state.

```python
# ❌ BAD: Tests depend on order
class TestOrdering:
    def test_create_product(self):
        Product.objects.create(name="Widget")  # Creates state

    def test_list_products(self):
        response = client.get(reverse("products:list"))
        assert "Widget" in response.content.decode()  # Depends on previous test!

# ✅ GOOD: Each test is self-contained
def test_create_product(client, admin_client):
    admin_client.post(reverse("products:create"), data={"name": "Widget"})
    assert Product.objects.filter(name="Widget").exists()

def test_list_products(client, product_factory):
    product_factory(name="Widget")  # Creates its own data
    response = client.get(reverse("products:list"))
    assert "Widget" in response.content.decode()
```

**Rule**: "If everybody cleans up after themselves, everyone benefits from a clean environment."

## 9. Composable

**Principle**: Avoid testing every combination (multiplicative trap).

**In Acceptance Tests**: Test components separately; trust composition.

```python
# ❌ BAD: Multiplicative testing
def test_visa_standard_shipping(): ...
def test_visa_express_shipping(): ...
def test_mastercard_standard_shipping(): ...
def test_mastercard_express_shipping(): ...
# 4 payment × 3 shipping = 12 tests!

# ✅ GOOD: Composable testing
def test_payment_charges_correct_amount(logged_in_client, order_factory):
    """Test payment in isolation."""
    ...

def test_shipping_calculates_correctly(client, cart_factory):
    """Test shipping in isolation."""
    ...

def test_checkout_combines_payment_and_shipping(logged_in_client, full_cart):
    """One test to verify composition."""
    ...
```

## 10. Specific

**Principle**: Failures should pinpoint the problem.

**In Acceptance Tests**: Use descriptive assertions.

```python
# ❌ BAD: Vague failure
def test_checkout(client):
    response = client.post(reverse("checkout"))
    assert response.status_code == 200  # Why did it fail?

# ✅ GOOD: Specific failure
def test_checkout_requires_address(logged_in_client, cart_with_items):
    response = logged_in_client.post(reverse("checkout"), data={
        "shipping_address": "",  # Deliberately missing
    })

    assert response.status_code == 400, "Expected validation error for missing address"
    errors = response.json().get("errors", {})
    assert "shipping_address" in errors, f"Expected address error, got: {errors}"
```

## 11. Predictive

**Principle**: Test results should predict production behavior.

**In Acceptance Tests**: Use real infrastructure wherever possible.

```python
# Acceptance tests are highly predictive because they:
# - Use real HTTP requests
# - Hit real database
# - Render real templates
# - Exercise real URL routing

# Only stub at true external boundaries:
@pytest.fixture
def stubbed_stripe():
    """Stub only the actual external API."""
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://api.stripe.com/v1/charges",
            json={"id": "ch_test", "status": "succeeded"}
        )
        yield rsps
```

**Beck's Insight**: Some conditions only occur in production. Don't chase 100% predictability—fill gaps as you discover them.

## 12. Inspiring

**Principle**: Tests should enable confident action.

**In Acceptance Tests**: Comprehensive coverage of user journeys.

When acceptance tests pass, you should feel confident to:
- Deploy to production
- Delete dead code
- Perform major refactors
- Try experimental features

```python
class TestCriticalUserJourneys:
    """These tests passing = safe to deploy."""

    def test_new_user_can_register(self, client): ...
    def test_user_can_complete_purchase(self, logged_in_client): ...
    def test_user_can_reset_password(self, client): ...
    def test_admin_can_manage_products(self, admin_client): ...
```

**The Goal**: "Engineers should always be making themselves obsolete every day"—tests automate verification so you can tackle new challenges.

## Trade-offs Summary

| Property | May Conflict With | Resolution |
|----------|-------------------|------------|
| Fast | Predictive | Stub external services only |
| Specific | Readable | Use helper functions with good names |
| Isolated | Fast | Use transactions, not truncation |
| Composable | Predictive | One integration test per composition point |

**Key Insight**: When properties conflict, prioritize based on context. For acceptance tests, predictiveness and behavioral sensitivity typically win.
