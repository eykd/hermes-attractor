# Safe Logger Implementation

**Purpose**: A JSON `logging.Formatter` plus a redaction-aware `LoggerAdapter` for production-safe structured logging.

## When to Use

Use this reference when implementing the core logging infrastructure that serializes records to JSON and automatically redacts sensitive fields based on environment. The `SafeLoggerAdapter` ensures PII and secrets never reach production logs while preserving debugging capability in development.

## Pattern

```python
# src/hermes_attractor/adapters/logging/safe_logger.py
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from hermes_attractor.adapters.logging.context import get_context
from hermes_attractor.adapters.logging.redaction import redact_value

_CRITICAL_FIELDS = frozenset({"password", "secret", "token", "api_key"})


class JsonFormatter(logging.Formatter):
    """Serialize each record to one JSON line, including correlation IDs."""

    def __init__(self, service: str, *, environment: str, version: str) -> None:
        super().__init__()
        self._service = service
        self._environment = environment
        self._version = version

    def format(self, record: logging.LogRecord) -> str:
        ctx = get_context()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": self._service,
            "environment": self._environment,
            "version": self._version,
            "request_id": ctx.request_id if ctx else "no-context",
            "event": getattr(record, "event", record.getMessage()),
        }
        if ctx and ctx.trace_id is not None:
            payload["trace_id"] = ctx.trace_id
        payload.update(getattr(record, "fields", {}))
        return json.dumps(payload, default=str)


class SafeLoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    """LoggerAdapter that redacts structured fields before they reach handlers."""

    def __init__(self, logger: logging.Logger, *, is_production: bool) -> None:
        super().__init__(logger, {})
        self._is_production = is_production

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        extra = dict(kwargs.get("extra") or {})
        fields = dict(extra.get("fields") or {})
        if self._is_production:
            # Full recursive redaction in production.
            fields = redact_value(fields)  # type: ignore[assignment]
        else:
            # In development, still redact the most critical fields.
            for key in list(fields):
                if key.lower() in _CRITICAL_FIELDS:
                    fields[key] = "[REDACTED]"
        extra["fields"] = fields
        kwargs["extra"] = extra
        return msg, kwargs
```

## Example Usage

```python
# src/hermes_attractor/use_cases/create_user.py
from hermes_attractor.adapters.logging import create_logger


class CreateUserUseCase:
    def execute(self, request: CreateUserRequest) -> UserResponse:
        logger = create_logger(
            service="user-api",
            environment="production",
            version="1.0.0",
        )

        logger.info(
            "create user started",
            extra={
                "event": "use_case.create_user.started",
                "fields": {
                    "category": "application",
                    "email": request.email,  # Masked to e***@domain.com by redaction
                },
            },
        )
        # Application logic...
```

## Edge Cases

### Missing Operation Context

**Scenario**: Logger used outside an operation context (e.g. a scheduled job)
**Solution**: The formatter falls back to `request_id = "no-context"`; document when context is unavailable.

```python
ctx = get_context()
request_id = ctx.request_id if ctx else "no-context"
```

### Non-Serializable Values in Log Fields

**Scenario**: Logging objects that `json.dumps` cannot serialize raises during `format()`.
**Solution**: Pass `default=str` to `json.dumps` (as above) so unknown values degrade to their `repr`, and never let a logging failure crash the request.

```python
try:
    line = json.dumps(payload, default=str)
except (TypeError, ValueError):
    line = json.dumps({"event": "logging.serialization_error"})
```

## Common Mistakes

### ❌ Mistake: Logging debug records in production

Debug logs in production waste resources and may expose sensitive data.

```python
# Bad: debug emitted regardless of environment
logger.setLevel(logging.DEBUG)
```

### ✅ Correct: Environment-aware level

Set the level from configuration so debug is suppressed in production.

```python
# Good: level driven by environment
level = logging.INFO if is_production else logging.DEBUG
logger.setLevel(level)
```

### ❌ Mistake: Redacting only specific fields by hand

Manual field-by-field redaction is error-prone and misses nested structures.

```python
# Bad: manual, shallow redaction
fields["password"] = "[REDACTED]"
fields["token"] = "[REDACTED]"
# What about nested dicts?
```

### ✅ Correct: Use comprehensive redact_value

Apply systematic redaction to the entire field dict.

```python
# Good: recursive redaction in production
if self._is_production:
    fields = redact_value(fields)
```

## Testing

```python
# tests/unit/adapters/logging/test_safe_logger.py
import json
import logging

from hermes_attractor.adapters.logging.safe_logger import JsonFormatter, SafeLoggerAdapter


def test_redacts_sensitive_fields_in_production(caplog):
    logger = logging.getLogger("test.prod")
    adapter = SafeLoggerAdapter(logger, is_production=True)

    with caplog.at_level(logging.INFO, logger="test.prod"):
        adapter.info(
            "user login",
            extra={"event": "user.login", "fields": {"password": "secret123", "email": "user@example.com"}},
        )

    record = caplog.records[0]
    assert record.fields["password"] == "[REDACTED]"


def test_json_formatter_emits_single_line():
    formatter = JsonFormatter("test", environment="test", version="1.0.0")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="msg", args=(), exc_info=None,
    )
    record.event = "test.event"
    record.fields = {"category": "application"}

    payload = json.loads(formatter.format(record))
    assert payload["event"] == "test.event"
    assert payload["category"] == "application"
    assert payload["request_id"] == "no-context"
```

## Related References

- [base-fields.md](./base-fields.md) - `BaseLogFields` schema definition
- [../../pii-redaction/references/redaction-functions.md](../../pii-redaction/references/redaction-functions.md) - Comprehensive redaction patterns
