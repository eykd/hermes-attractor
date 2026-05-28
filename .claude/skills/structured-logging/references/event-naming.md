# Event Naming Conventions

**Purpose**: Standardized event naming patterns for consistent log categorization and querying.

## When to Use

Use this reference when naming log events (the `event` field) to ensure consistency across your application. Proper event naming enables filtering, alerting, and analysis by following a hierarchical dot-notation convention that clearly communicates what happened.

## Pattern

Use dot-notation following this structure:

```
{domain}.{entity}.{action}[.{outcome}]
```

**Components:**

- **domain**: Business area or layer (e.g. `user`, `task`, `payment`, `http`, `db`)
- **entity**: The thing being acted upon (e.g. `login`, `task`, `charge`, `request`, `query`)
- **action**: What happened (e.g. `created`, `updated`, `deleted`, `received`, `sent`, `executed`)
- **outcome**: Optional result (e.g. `succeeded`, `failed`, `already_completed`)

## Decision Matrix

| Log Category   | Event Pattern                      | Example Events                                          |
| -------------- | ---------------------------------- | ------------------------------------------------------- |
| Domain         | `{aggregate}.{action}[.{outcome}]` | `task.completed`, `user.registered.failed`              |
| Application    | `{layer}.{entity}.{action}`        | `use_case.create_task.started`, `http.request.received` |
| Infrastructure | `{system}.{operation}.{outcome}`   | `db.query.succeeded`, `cache.hit`, `api.call.timeout`   |

## Example Usage

### Domain Events

```python
logger.info(
    "task completed",
    extra={"event": "task.completed",
           "fields": {"category": "domain", "aggregate_type": "Task",
                      "aggregate_id": "task-123", "domain_event": "TaskCompleted"}},
)

logger.info(
    "login succeeded",
    extra={"event": "user.login.succeeded",
           "fields": {"category": "domain", "user_id": "user-456"}},
)

logger.warning(
    "charge failed",
    extra={"event": "payment.charge.failed",
           "fields": {"category": "domain", "aggregate_type": "Payment",
                      "aggregate_id": "pay-789", "error_code": "INSUFFICIENT_FUNDS"}},
)
```

### Application Events

```python
logger.info(
    "request received",
    extra={"event": "http.request.received",
           "fields": {"category": "application", "http_method": "POST", "http_path": "/tasks"}},
)

logger.info(
    "complete task started",
    extra={"event": "use_case.complete_task.started",
           "fields": {"category": "application", "task_id": "task-123"}},
)

logger.warning(
    "validation failed",
    extra={"event": "use_case.complete_task.validation_failed",
           "fields": {"category": "application", "validation_errors": 3}},
)
```

### Infrastructure Events

```python
logger.info(
    "query succeeded",
    extra={"event": "db.query.succeeded",
           "fields": {"category": "infrastructure", "query_type": "SELECT",
                      "table": "tasks", "duration_ms": 12}},
)

logger.info(
    "cache hit",
    extra={"event": "cache.hit",
           "fields": {"category": "infrastructure", "cache_key": "user:123:profile"}},
)

logger.error(
    "api call timeout",
    extra={"event": "api.call.timeout",
           "fields": {"category": "infrastructure",
                      "api_endpoint": "https://payment-gateway.example.com",
                      "timeout_ms": 5000}},
)
```

## Common Event Patterns

| Pattern                       | Description           | Example                        |
| ----------------------------- | --------------------- | ------------------------------ |
| `{entity}.created`            | Entity creation       | `task.created`                 |
| `{entity}.updated`            | Entity modification   | `task.updated`                 |
| `{entity}.deleted`            | Entity deletion       | `task.deleted`                 |
| `{entity}.{action}.succeeded` | Successful operation  | `user.login.succeeded`         |
| `{entity}.{action}.failed`    | Failed operation      | `payment.charge.failed`        |
| `http.{lifecycle}`            | HTTP request/response | `http.request.received`        |
| `use_case.{name}.{phase}`     | Use case execution    | `use_case.create_task.started` |
| `db.{operation}.{outcome}`    | Database interaction  | `db.query.succeeded`           |
| `cache.{result}`              | Cache interaction     | `cache.hit`, `cache.miss`      |

## Edge Cases

### Multiple Outcomes for the Same Action

**Scenario**: An action can have multiple terminal states.
**Solution**: Use specific outcome suffixes.

```python
logger.info("charge succeeded", extra={"event": "payment.charge.succeeded", "fields": {"category": "domain"}})
logger.warning("charge declined", extra={"event": "payment.charge.declined", "fields": {"category": "domain"}})
logger.error("charge failed", extra={"event": "payment.charge.failed", "fields": {"category": "domain"}})
logger.info("charge refunded", extra={"event": "payment.charge.refunded", "fields": {"category": "domain"}})
```

### Compound Actions

**Scenario**: An operation involves multiple steps.
**Solution**: Use hierarchical naming with step indicators.

```python
logger.info("validation started", extra={"event": "user.registration.validation.started", "fields": {"category": "application"}})
logger.info("email sent", extra={"event": "user.registration.email.sent", "fields": {"category": "application"}})
logger.info("registration completed", extra={"event": "user.registration.completed", "fields": {"category": "domain"}})
```

## Common Mistakes

### ❌ Mistake: Using sentence-like event names

Natural-language event names are inconsistent and hard to query.

```python
# Bad: inconsistent naming
logger.info("User has logged in successfully", extra={"event": "User has logged in successfully"})
```

### ✅ Correct: Use dot-notation convention

```python
# Good: consistent convention
logger.info("login succeeded", extra={"event": "user.login.succeeded", "fields": {"category": "domain"}})
```

### ❌ Mistake: Too generic or too specific

Balance between overly broad and overly detailed event names.

```python
# Bad: too generic
logger.info("event", extra={"event": "event"})

# Bad: too specific
logger.info("login", extra={"event": "user.login.with.email.and.password.succeeded.on.production"})
```

### ✅ Correct: Appropriate granularity

Use the event name for identity, additional fields for context.

```python
# Good: balanced name + contextual fields
logger.info(
    "login succeeded",
    extra={"event": "user.login.succeeded",
           "fields": {"category": "domain", "auth_method": "email_password"}},
)
```

## Testing

```python
# tests/unit/adapters/logging/test_event_naming.py
import re

import pytest

_PATTERN = re.compile(r"^[a-z_]+(\.[a-z_]+)+$")


@pytest.mark.parametrize(
    "event",
    [
        "task.created",
        "user.login.succeeded",
        "payment.charge.failed",
        "http.request.received",
        "db.query.succeeded",
        "use_case.create_task.started",
    ],
)
def test_event_follows_dot_notation(event: str) -> None:
    assert _PATTERN.match(event)
    assert not re.search(r"[A-Z]", event)  # no PascalCase/camelCase
    assert "-" not in event  # no kebab-case
```

## Related References

- [base-fields.md](./base-fields.md) - The `event` field in the schema
- [../../log-categorization/references/decision-matrix.md](../../log-categorization/references/decision-matrix.md) - Categorizing logs by event type
