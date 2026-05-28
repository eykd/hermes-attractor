# Breadcrumbs

**Purpose**: Track event sequences leading to errors using Sentry breadcrumbs for enhanced debugging context.

## When to Use

Use this reference when you need to track user actions, application state changes, or external service calls that provide context for error investigation. Breadcrumbs are automatically attached to any exception captured afterwards in the same scope.

## Pattern

```python
# src/hermes_attractor/use_cases/create_payment.py
import sentry_sdk


class CreatePaymentUseCase:
    def execute(self, request: CreatePaymentRequest) -> PaymentResult:
        sentry_sdk.add_breadcrumb(
            category="payment",
            message="Starting payment processing",
            level="info",
            data={"amount": request.amount, "currency": request.currency},  # never card numbers!
        )

        result = self._payment_gateway.charge(request)

        sentry_sdk.add_breadcrumb(
            category="payment",
            message="Payment processed successfully",
            level="info",
            data={"transaction_id": result.transaction_id},
        )
        return result
        # If an exception propagates, the breadcrumbs above are included in the report.
```

## Breadcrumb Categories

| Category     | Use Case         | Example                         |
| ------------ | ---------------- | ------------------------------- |
| `http`       | HTTP requests    | External API calls, webhooks    |
| `navigation` | Route changes    | Page transitions, redirects     |
| `user`       | User actions     | Button clicks, form submissions |
| `console`    | Console/log lines | Debug messages                 |
| `query`      | Database queries | SQLite/repository operations    |

## Breadcrumb Levels

| Level     | When to Use              |
| --------- | ------------------------ |
| `debug`   | Detailed diagnostic info |
| `info`    | Normal operations        |
| `warning` | Unexpected but handled   |
| `error`   | Failure events           |

## Example Usage

```python
# src/hermes_attractor/adapters/sqlite_task_repository.py
import sentry_sdk


class SqliteTaskRepository:
    def save(self, task: Task) -> None:
        sentry_sdk.add_breadcrumb(
            category="query",
            message="Saving task",
            level="debug",
            data={"task_id": task.id, "operation": "INSERT"},
        )

        self._conn.execute("INSERT INTO tasks ...", (task.id,))

        sentry_sdk.add_breadcrumb(
            category="query",
            message="Task saved successfully",
            level="info",
            data={"task_id": task.id},
        )
```

## Edge Cases

### Breadcrumb Limit

**Scenario**: Sentry keeps only the most recent breadcrumbs (default 100) per event.
**Solution**: Breadcrumbs are automatically capped; older entries are dropped. Don't rely on early breadcrumbs surviving a long-running operation.

### High-Frequency Breadcrumbs

**Scenario**: Adding breadcrumbs inside a hot loop.
**Solution**: Aggregate instead of emitting one per iteration.

```python
# Bad - too many breadcrumbs
for item in items:
    sentry_sdk.add_breadcrumb(message=f"Processing {item.id}")

# Good - one aggregate breadcrumb
sentry_sdk.add_breadcrumb(message="Processing items", data={"count": len(items)})
```

## Common Mistakes

### ❌ Mistake: Including sensitive data in breadcrumbs

```python
# Bad - includes a password
sentry_sdk.add_breadcrumb(
    category="user",
    message="User login attempt",
    data={"username": user.username, "password": credentials.password},  # never log passwords!
)
```

**Why it's wrong**: Breadcrumbs are sent to Sentry and may expose sensitive data.

### ✅ Correct: Use safe identifiers only

```python
# Good - no sensitive data
sentry_sdk.add_breadcrumb(
    category="user",
    message="User login attempt",
    data={"user_id": user.id},
)
```

## Testing

```python
# tests/unit/use_cases/test_create_payment.py
from unittest.mock import patch


def test_adds_breadcrumb_before_payment_processing():
    use_case = CreatePaymentUseCase(fake_gateway)
    with patch("hermes_attractor.use_cases.create_payment.sentry_sdk") as sentry:
        use_case.execute(CreatePaymentRequest(amount=100, currency="USD"))

        first_call = sentry.add_breadcrumb.call_args_list[0]
        assert first_call.kwargs["category"] == "payment"
        assert first_call.kwargs["message"] == "Starting payment processing"
```

## Related References

- [context-management.md](./context-management.md) - Add persistent context to all errors
- [error-capture.md](./error-capture.md) - Capture errors with breadcrumb history
