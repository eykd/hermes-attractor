# Context Management

**Purpose**: Add custom context to Sentry events — user identification, tags for filtering, and custom context objects for debugging.

## When to Use

Use this reference when you need to add user context for error tracking, set tags for filtering errors in the Sentry dashboard, or attach custom context objects with additional debugging information.

## Pattern

```python
# src/hermes_attractor/adapters/observability/sentry_context.py
from __future__ import annotations

import sentry_sdk

from hermes_attractor.adapters.logging.url_redaction import redact_url


def set_sentry_context(request: Request, user_id: str | None = None) -> None:
    # Set user context without PII.
    if user_id:
        sentry_sdk.set_user({"id": user_id})  # internal id only — no email/username/ip

    # Tags for filtering in the dashboard.
    sentry_sdk.set_tag("request_path", request.path)

    # Structured context for debugging.
    sentry_sdk.set_context("request", {
        "method": request.method,
        "url": redact_url(request.url),
    })
```

> When `sentry-sdk` is not installed, calling these functions would raise `NameError`/`ImportError`. Keep all Sentry calls inside the observability adapter and only invoke them after `init_sentry()` returned `True`, or guard the import.

## Context Types

| Function                   | Purpose                          | Example Use Case                          |
| -------------------------- | -------------------------------- | ----------------------------------------- |
| `sentry_sdk.set_user()`    | Identify user for error grouping | Track errors by user_id                   |
| `sentry_sdk.set_tag()`     | Add filterable metadata          | Filter by country, path, feature          |
| `sentry_sdk.set_context()` | Add structured debug data        | Attach request details, environment state |

## Example Usage

```python
# src/hermes_attractor/use_cases/complete_task.py
import sentry_sdk


class CompleteTaskUseCase:
    def execute(self, request: CompleteTaskRequest) -> CompleteTaskResponse:
        # Correlate errors with the user (internal id only).
        sentry_sdk.set_user({"id": request.user_id})

        # Tags for filtering.
        sentry_sdk.set_tag("use_case", "complete_task")
        sentry_sdk.set_tag("task_id", request.task_id)

        # Custom context for debugging (no sensitive data).
        sentry_sdk.set_context("task", {"task_id": request.task_id, "user_id": request.user_id})

        # Use case logic...
```

## Scoped Context

Prefer `push_scope` (or `sentry_sdk.new_scope()` in SDK v2) when context should apply to a single operation rather than the whole request:

```python
import sentry_sdk

with sentry_sdk.new_scope() as scope:
    scope.set_tag("use_case", "complete_task")
    scope.set_context("task", {"task_id": task_id})
    # Anything captured inside this block carries the scoped context.
```

## Edge Cases

### Multiple user context calls

**Scenario**: Setting user context more than once in the same request.
**Solution**: Last call wins — Sentry replaces the previous user context.

```python
sentry_sdk.set_user({"id": "user-123"})
# Later in the request lifecycle:
sentry_sdk.set_user({"id": "user-123", "ip_address": None})
```

### Clearing context

**Scenario**: Need to remove user context (e.g. after logout).
**Solution**: Set user to `None`.

```python
sentry_sdk.set_user(None)
```

## Common Mistakes

### ❌ Mistake: Including PII in user context

```python
# Bad - includes email and username
sentry_sdk.set_user({"id": user.id, "email": user.email, "username": user.username})
```

**Why it's wrong**: Violates privacy regulations and exposes sensitive data.

### ✅ Correct: Use only a non-PII identifier

```python
# Good - internal identifier only
sentry_sdk.set_user({"id": user.id})
```

### ❌ Mistake: Not redacting URLs with sensitive query params

```python
# Bad - exposes token in URL
sentry_sdk.set_context("request", {"url": request.url})  # may contain ?token=secret
```

### ✅ Correct: Redact sensitive URL parameters

```python
# Good - reuse the pii-redaction helper
sentry_sdk.set_context("request", {"url": redact_url(request.url)})
```

## Testing

```python
# tests/unit/adapters/observability/test_sentry_context.py
from unittest.mock import patch

from hermes_attractor.adapters.observability.sentry_context import set_sentry_context


def test_sets_user_context_with_user_id():
    request = FakeRequest(method="GET", path="/tasks", url="https://example.com/tasks")
    with patch("hermes_attractor.adapters.observability.sentry_context.sentry_sdk") as sentry:
        set_sentry_context(request, "user-123")
        sentry.set_user.assert_called_once_with({"id": "user-123"})


def test_sets_request_path_tag():
    request = FakeRequest(method="GET", path="/tasks", url="https://example.com/tasks")
    with patch("hermes_attractor.adapters.observability.sentry_context.sentry_sdk") as sentry:
        set_sentry_context(request)
        sentry.set_tag.assert_any_call("request_path", "/tasks")
```

## Related References

- [breadcrumbs.md](./breadcrumbs.md) - Add event sequence tracking with breadcrumbs
- [error-capture.md](./error-capture.md) - Capture errors with context-specific tags
