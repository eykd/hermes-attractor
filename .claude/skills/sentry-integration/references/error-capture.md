# Error Capture

**Purpose**: Manually capture exceptions with Sentry including tags, extra context, and severity levels for enhanced error tracking.

## When to Use

Use this reference when you need to manually capture errors with additional context, set custom severity levels, or capture non-error conditions that require tracking.

## Pattern

```python
# src/hermes_attractor/use_cases/create_payment.py
import sentry_sdk


class CreatePaymentUseCase:
    def execute(self, request: CreatePaymentRequest) -> PaymentResult:
        try:
            return self._payment_gateway.charge(request)
        except PaymentGatewayError as exc:
            with sentry_sdk.new_scope() as scope:
                scope.set_tag("payment_provider", "stripe")
                scope.set_tag("payment_type", request.type)
                scope.set_extra("amount", request.amount)
                scope.set_extra("currency", request.currency)  # debugging info, no PII
                sentry_sdk.capture_exception(exc)
            raise
```

## Capture Methods

| Method                              | Use Case                | When to Use                 |
| ----------------------------------- | ----------------------- | --------------------------- |
| `sentry_sdk.capture_exception(exc)` | Capture an exception    | Standard exception handling |
| `sentry_sdk.capture_message(msg, level)` | Capture a string message | Non-error conditions     |
| `sentry_sdk.capture_event(event)`   | Full control            | Custom event structure      |

## Severity Levels

```python
import sentry_sdk

# Informational
sentry_sdk.capture_message("User completed onboarding", level="info")

# Warning
sentry_sdk.capture_message("API rate limit approaching", level="warning")

# Error / fatal — set the level on the scope before capturing
with sentry_sdk.new_scope() as scope:
    scope.level = "fatal"
    sentry_sdk.capture_exception(exc)
```

## Example Usage with Tags and Extra Data

```python
# src/hermes_attractor/adapters/sqlite_task_repository.py
import sentry_sdk


class SqliteTaskRepository:
    def save(self, task: Task) -> None:
        try:
            self._conn.execute("INSERT INTO tasks ...", (task.id,))
        except Exception as exc:
            with sentry_sdk.new_scope() as scope:
                scope.set_tag("repository", "SqliteTaskRepository")
                scope.set_tag("operation", "save")
                scope.set_tag("table", "tasks")
                scope.set_extra("task_id", task.id)  # non-sensitive debugging info
                sentry_sdk.capture_exception(exc)
            raise
```

## Logging Integration

Rather than capturing every error by hand, the `LoggingIntegration` can forward records emitted through the stdlib `logging` module (see the structured-logging skill). Configure it explicitly so you control what becomes a Sentry *event* vs a *breadcrumb*:

```python
from sentry_sdk.integrations.logging import LoggingIntegration

logging_integration = LoggingIntegration(
    level="INFO",        # capture INFO+ as breadcrumbs
    event_level="ERROR", # send ERROR+ as Sentry events
)
sentry_sdk.init(dsn=dsn, integrations=[logging_integration])
```

With this enabled, `logger.error(...)` and `logger.exception(...)` produce Sentry events automatically, and your structured fields (passed via `extra={"fields": ...}`) ride along. Combine with the pii-redaction `RedactionFilter` so scrubbing happens before the integration sees the record.

## Edge Cases

### Capturing non-exception conditions

**Scenario**: An external API returns `{"error": "..."}` rather than raising.
**Solution**: Wrap in an exception or use `capture_message`.

```python
result = external_api.call()
if result.error:
    with sentry_sdk.new_scope() as scope:
        scope.set_extra("api_response", result.as_dict())
        sentry_sdk.capture_message(result.error, level="error")
```

### Sampling high-volume errors

**Scenario**: High error rates may exhaust Sentry quota.
**Solution**: Sample in `before_send`.

```python
import random


def before_send(event, _hint):
    values = event.get("exception", {}).get("values", [])
    if values and values[0].get("type") == "ValidationError":
        if random.random() > 0.1:  # keep only 10% of validation errors
            return None
    return event
```

## Common Mistakes

### ❌ Mistake: Swallowing captured errors

```python
# Bad - error captured but not propagated
try:
    risky_operation()
except Exception as exc:
    sentry_sdk.capture_exception(exc)
    # caller never learns the operation failed
```

### ✅ Correct: Capture and re-raise

```python
# Good - captured AND propagated
try:
    risky_operation()
except Exception as exc:
    sentry_sdk.capture_exception(exc)
    raise
```

### ❌ Mistake: Including PII in extra data

```python
# Bad - includes email and phone
with sentry_sdk.new_scope() as scope:
    scope.set_extra("user_email", user.email)
    scope.set_extra("user_phone", user.phone)
    sentry_sdk.capture_exception(exc)
```

### ✅ Correct: Use non-PII identifiers

```python
# Good - internal id only
with sentry_sdk.new_scope() as scope:
    scope.set_extra("user_id", user.id)
    sentry_sdk.capture_exception(exc)
```

## Testing

```python
# tests/unit/use_cases/test_create_payment.py
from unittest.mock import patch

import pytest


def test_captures_exception_with_payment_context():
    gateway = FakeGateway(raises=PaymentGatewayError("Payment failed"))
    use_case = CreatePaymentUseCase(gateway)

    with patch("hermes_attractor.use_cases.create_payment.sentry_sdk") as sentry:
        with pytest.raises(PaymentGatewayError, match="Payment failed"):
            use_case.execute(CreatePaymentRequest(amount=100, currency="USD", type="card"))

        sentry.capture_exception.assert_called_once()
```

## Related References

- [breadcrumbs.md](./breadcrumbs.md) - Add event sequences automatically included in error reports
- [context-management.md](./context-management.md) - Set persistent context attached to all errors
