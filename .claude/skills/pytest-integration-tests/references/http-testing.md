# HTTP Adapter Integration Testing

## Core Principles

1. **Never hit real external services** — Use controlled fakes
2. **Verify outgoing requests** — Assert on what your code sends
3. **Test response interpretation** — Verify your adapter's parsing logic
4. **Test error scenarios** — Timeouts, 4xx, 5xx, malformed responses

## Libraries

| Library | Best For | Install |
|---------|----------|---------|
| `responses` | requests library | `uv add --group=test responses` |
| `requests-mock` | requests library | `uv add --group=test requests-mock` |
| `httpx-mock` | httpx library | `uv add --group=test pytest-httpx` |
| `respx` | httpx library | `uv add --group=test respx` |
| `aioresponses` | aiohttp | `uv add --group=test aioresponses` |

## Testing with `responses`

### Basic Usage

```python
import responses
import pytest
from myapp.adapters.payment import PaymentGatewayAdapter


class TestPaymentGatewayAdapter:

    @pytest.fixture
    def adapter(self):
        return PaymentGatewayAdapter(api_key="test_key")

    @responses.activate
    def test_successful_charge(self, adapter):
        # Given: API will return success
        responses.add(
            responses.POST,
            "https://api.stripe.com/v1/charges",
            json={"id": "ch_123", "status": "succeeded", "amount": 5000},
            status=200,
        )

        # When
        result = adapter.charge(amount=50.00, token="tok_visa")

        # Then: Result is interpreted correctly
        assert result.success is True
        assert result.transaction_id == "ch_123"

        # And: Request was correct
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert "amount=5000" in request.body
        assert "Bearer test_key" in request.headers.get("Authorization", "")

    @responses.activate
    def test_declined_card(self, adapter):
        responses.add(
            responses.POST,
            "https://api.stripe.com/v1/charges",
            json={
                "error": {
                    "type": "card_error",
                    "code": "card_declined",
                    "message": "Your card was declined."
                }
            },
            status=402,
        )

        result = adapter.charge(amount=50.00, token="tok_declined")

        assert result.success is False
        assert result.error_code == "card_declined"
        assert "declined" in result.error_message.lower()

    @responses.activate
    def test_timeout_returns_retriable_error(self, adapter):
        responses.add(
            responses.POST,
            "https://api.stripe.com/v1/charges",
            body=responses.ConnectionError("Connection timed out"),
        )

        result = adapter.charge(amount=50.00, token="tok_visa")

        assert result.success is False
        assert result.is_retriable is True
```

### Callback Responses

```python
@responses.activate
def test_dynamic_response(adapter):
    def request_callback(request):
        body = dict(parse_qsl(request.body))
        amount = int(body.get("amount", 0))

        if amount > 100000:  # Over $1000
            return (402, {}, json.dumps({"error": {"code": "amount_too_large"}}))
        return (200, {}, json.dumps({"id": "ch_123", "status": "succeeded"}))

    responses.add_callback(
        responses.POST,
        "https://api.stripe.com/v1/charges",
        callback=request_callback,
    )

    # Small amount succeeds
    result = adapter.charge(amount=50.00, token="tok_visa")
    assert result.success

    # Large amount fails
    result = adapter.charge(amount=2000.00, token="tok_visa")
    assert not result.success
```

## Reusable Fake HTTP Fixture

```python
# tests/integration/conftest.py
import pytest
import responses


@pytest.fixture
def fake_stripe():
    """Reusable fixture for Stripe API mocking."""

    class FakeStripe:
        def __init__(self):
            self._mock = responses.RequestsMock()
            self._mock.start()

        def stub_successful_charge(self, charge_id="ch_test", amount=None):
            self._mock.add(
                responses.POST,
                "https://api.stripe.com/v1/charges",
                json={
                    "id": charge_id,
                    "status": "succeeded",
                    "amount": amount or 0,
                },
                status=200,
            )
            return self

        def stub_declined(self, code="card_declined", message="Card was declined"):
            self._mock.add(
                responses.POST,
                "https://api.stripe.com/v1/charges",
                json={"error": {"code": code, "message": message}},
                status=402,
            )
            return self

        def stub_server_error(self):
            self._mock.add(
                responses.POST,
                "https://api.stripe.com/v1/charges",
                json={"error": {"type": "api_error"}},
                status=500,
            )
            return self

        def stub_timeout(self):
            self._mock.add(
                responses.POST,
                "https://api.stripe.com/v1/charges",
                body=responses.ConnectionError("timeout"),
            )
            return self

        def assert_charge_requested(self, amount_cents=None, token=None):
            assert len(self._mock.calls) > 0, "No requests made"
            body = self._mock.calls[-1].request.body
            if amount_cents:
                assert f"amount={amount_cents}" in body
            if token:
                assert f"source={token}" in body

        @property
        def call_count(self):
            return len(self._mock.calls)

        def stop(self):
            self._mock.stop()
            self._mock.reset()

    fake = FakeStripe()
    yield fake
    fake.stop()


# Usage:
def test_payment_flow(fake_stripe, payment_adapter):
    fake_stripe.stub_successful_charge(charge_id="ch_abc123")

    result = payment_adapter.charge(amount=25.00, token="tok_visa")

    assert result.success
    fake_stripe.assert_charge_requested(amount_cents=2500)
```

## Testing with `httpx` and `respx`

```python
import respx
import httpx
import pytest


@pytest.fixture
def async_adapter():
    return AsyncPaymentAdapter(api_key="test_key")


@respx.mock
async def test_async_charge(async_adapter):
    respx.post("https://api.example.com/charges").mock(
        return_value=httpx.Response(
            200,
            json={"id": "ch_123", "status": "succeeded"}
        )
    )

    result = await async_adapter.charge(amount=50.00)

    assert result.success
    assert respx.calls.call_count == 1
```

## Testing Multiple API Calls

```python
@responses.activate
def test_retry_on_rate_limit(adapter):
    # First call: rate limited
    responses.add(
        responses.POST,
        "https://api.example.com/resource",
        json={"error": "rate_limited"},
        status=429,
        headers={"Retry-After": "1"},
    )
    # Second call: success
    responses.add(
        responses.POST,
        "https://api.example.com/resource",
        json={"id": "123"},
        status=200,
    )

    result = adapter.create_resource(data={"name": "test"})

    assert result.success
    assert len(responses.calls) == 2


@responses.activate
def test_workflow_with_multiple_endpoints(adapter):
    # Step 1: Create customer
    responses.add(
        responses.POST,
        "https://api.example.com/customers",
        json={"id": "cust_123"},
        status=201,
    )
    # Step 2: Create subscription
    responses.add(
        responses.POST,
        "https://api.example.com/subscriptions",
        json={"id": "sub_456", "customer": "cust_123"},
        status=201,
    )

    result = adapter.create_customer_with_subscription(
        email="test@example.com",
        plan="pro"
    )

    assert result.customer_id == "cust_123"
    assert result.subscription_id == "sub_456"
```

## Testing Error Scenarios

### HTTP Errors

```python
@pytest.mark.parametrize("status,expected_error", [
    (400, "bad_request"),
    (401, "unauthorized"),
    (403, "forbidden"),
    (404, "not_found"),
    (500, "server_error"),
    (502, "bad_gateway"),
    (503, "service_unavailable"),
])
@responses.activate
def test_handles_http_errors(adapter, status, expected_error):
    responses.add(
        responses.GET,
        "https://api.example.com/resource/123",
        status=status,
    )

    result = adapter.get_resource("123")

    assert result.success is False
    assert result.error_type == expected_error
```

### Network Errors

```python
@responses.activate
def test_handles_connection_error(adapter):
    responses.add(
        responses.POST,
        "https://api.example.com/resource",
        body=responses.ConnectionError("Connection refused"),
    )

    result = adapter.create_resource({})

    assert result.success is False
    assert result.is_retriable is True


@responses.activate
def test_handles_timeout(adapter):
    responses.add(
        responses.POST,
        "https://api.example.com/resource",
        body=requests.exceptions.Timeout("Request timed out"),
    )

    result = adapter.create_resource({})

    assert result.success is False
    assert result.error_type == "timeout"
```

### Malformed Responses

```python
@responses.activate
def test_handles_invalid_json(adapter):
    responses.add(
        responses.GET,
        "https://api.example.com/resource/123",
        body="not valid json",
        status=200,
    )

    result = adapter.get_resource("123")

    assert result.success is False
    assert result.error_type == "parse_error"


@responses.activate
def test_handles_unexpected_schema(adapter):
    responses.add(
        responses.GET,
        "https://api.example.com/resource/123",
        json={"unexpected": "schema"},
        status=200,
    )

    result = adapter.get_resource("123")

    # Adapter should handle gracefully
    assert result.success is False or result.id is None
```

## Testing Request Details

```python
@responses.activate
def test_sends_correct_headers(adapter):
    responses.add(responses.POST, "https://api.example.com/resource", status=200)

    adapter.create_resource({})

    request = responses.calls[0].request
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["Authorization"] == "Bearer test_key"
    assert request.headers["User-Agent"].startswith("MyApp/")


@responses.activate
def test_sends_correct_payload(adapter):
    responses.add(responses.POST, "https://api.example.com/resource", status=200)

    adapter.create_resource({
        "name": "Test Resource",
        "type": "premium",
        "metadata": {"key": "value"}
    })

    request = responses.calls[0].request
    payload = json.loads(request.body)

    assert payload["name"] == "Test Resource"
    assert payload["type"] == "premium"
    assert payload["metadata"]["key"] == "value"
```

## Testing Authentication Flows

```python
@responses.activate
def test_refreshes_token_on_401(adapter):
    # First call: unauthorized
    responses.add(
        responses.GET,
        "https://api.example.com/resource",
        status=401,
    )
    # Token refresh
    responses.add(
        responses.POST,
        "https://api.example.com/oauth/token",
        json={"access_token": "new_token"},
        status=200,
    )
    # Retry with new token
    responses.add(
        responses.GET,
        "https://api.example.com/resource",
        json={"id": "123"},
        status=200,
    )

    result = adapter.get_resource()

    assert result.success
    assert len(responses.calls) == 3

    # Verify new token was used
    final_request = responses.calls[2].request
    assert "new_token" in final_request.headers["Authorization"]
```

## Fixture for Blocking External Calls

```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def block_external_http(monkeypatch):
    """Prevent any test from making real HTTP requests."""
    def block(*args, **kwargs):
        raise RuntimeError(
            "HTTP request attempted but not mocked. "
            "Use responses.activate or mock the request."
        )

    monkeypatch.setattr("requests.Session.request", block)
    monkeypatch.setattr("urllib.request.urlopen", block)
```
