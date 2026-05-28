# Base Log Fields Schema

**Purpose**: `BaseLogFields` definition and required fields by log category.

## When to Use

Use this reference when defining the structured logging schema for your application. `BaseLogFields` establishes the fields present on every log entry, ensuring consistency and queryability across all logs. Additional `TypedDict`s extend the base for domain, application, and infrastructure contexts.

In Python, model the schema with `TypedDict` so `pyright --strict` can check the field names you pass to the logger, while still allowing extra event-specific fields.

## Pattern

```python
# src/hermes_attractor/adapters/logging/schema.py
from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

# Severity levels following RFC 5424 (syslog), mapped onto stdlib logging levels.
LogLevel = Literal["debug", "info", "warning", "error", "critical"]
LogCategory = Literal["domain", "application", "infrastructure"]


class BaseLogFields(TypedDict):
    """Fields attached to every structured log entry (via ``extra={"fields": ...}``)."""

    # Classification
    category: LogCategory
    # Optional correlation / timing (request_id and timestamp are added by the formatter)
    duration_ms: NotRequired[float]
    trace_id: NotRequired[str]
    span_id: NotRequired[str]


class IdentityFields(TypedDict, total=False):
    """Optional identity fields (redacted/masked by default)."""

    user_id: str
    session_id: str
    tenant_id: str


class RequestContext(TypedDict, total=False):
    """Application-layer request context."""

    http_method: str
    http_path: str  # path only, no query string
    http_status: int


class ErrorContext(TypedDict, total=False):
    """Error context."""

    error_code: str
    error_message: str  # safe message only
    error_type: str
    # Include a traceback only in non-production; logging.exception() also captures exc_info.


class DomainEventFields(TypedDict, total=False):
    """Domain event fields."""

    aggregate_type: str  # e.g. "Task", "User"
    aggregate_id: str
    domain_event: str  # e.g. "TaskCompleted"
```

When you log, you build a plain `dict` from these shapes and pass it as `extra={"event": ..., "fields": fields}`. The formatter injects `timestamp`, `level`, `service`, `environment`, `version`, and `request_id`.

## Decision Matrix

| Field Category     | Required For     | Purpose                        | Example Value            |
| ------------------ | ---------------- | ------------------------------ | ------------------------ |
| **Correlation**    | All logs         | Trace operations across layers | `request_id` (auto)      |
| **Timing**         | All logs         | Temporal ordering              | `timestamp` (auto)       |
| **Context**        | All logs         | Environment identification     | `service: "task-api"`    |
| **Classification** | All logs         | Severity and category          | `level: "error"`         |
| **Identity**       | Application logs | User/session tracking          | `user_id: "user-456"`    |
| **HTTP Context**   | Application logs | Request/response details       | `http_status: 200`       |
| **Error**          | Error logs       | Exception details              | `error_type: "ValueError"` |
| **Domain Event**   | Domain logs      | Business event identification  | `aggregate_type: "Task"` |

## Required Fields by Log Category

`request_id`, `timestamp`, `service`, `environment`, `level`, and `event` are added automatically by the formatter for every category. The fields below are passed in `fields=`:

| Field            | Domain | Application | Infrastructure |
| ---------------- | ------ | ----------- | -------------- |
| `category`       | ✓      | ✓           | ✓              |
| `aggregate_type` | ✓      |             |                |
| `aggregate_id`   | ✓      |             |                |
| `domain_event`   | ✓      |             |                |
| `http_method`    |        | ✓           |                |
| `http_path`      |        | ✓           |                |
| `http_status`    |        | ✓           |                |
| `duration_ms`    |        | ✓           | ✓              |

## Example Usage

```python
# Domain log
logger.info(
    "task completed",
    extra={"event": "task.completed",
           "fields": {"category": "domain", "aggregate_type": "Task",
                      "aggregate_id": "task-456", "domain_event": "TaskCompleted"}},
)

# Application log
logger.info(
    "response sent",
    extra={"event": "http.response.sent",
           "fields": {"category": "application", "http_method": "POST",
                      "http_path": "/tasks", "http_status": 201, "duration_ms": 45}},
)

# Infrastructure log
logger.info(
    "query succeeded",
    extra={"event": "db.query.succeeded",
           "fields": {"category": "infrastructure", "query_type": "INSERT",
                      "table": "tasks", "duration_ms": 12}},
)
```

## Edge Cases

### Optional Fields

**Scenario**: Not all logs have `trace_id` or `span_id`.
**Solution**: Mark them `NotRequired`/`total=False` so they may be omitted.

```python
class BaseLogFields(TypedDict):
    category: LogCategory
    trace_id: NotRequired[str]  # only when distributed tracing is active
```

### Dynamic Additional Fields

**Scenario**: Domain-specific fields vary by event.
**Solution**: `fields` is ultimately a `dict[str, Any]`. Use the `TypedDict`s to type the common shapes and add extra keys freely; the formatter merges whatever is present.

## Common Mistakes

### ❌ Mistake: Making every field required

Forcing all fields to be required makes logging verbose and `pyright` will reject valid call sites.

```python
# Bad: trace_id is not always available
class BaseLogFields(TypedDict):
    category: LogCategory
    trace_id: str  # required → every call must supply it
    user_id: str   # not present in all contexts
```

### ✅ Correct: Required core, optional context

```python
# Good
class BaseLogFields(TypedDict):
    category: LogCategory
    trace_id: NotRequired[str]
```

### ❌ Mistake: Logging PII in ad-hoc field names

Sensitive data under a non-standard key bypasses field-name-based redaction.

```python
# Bad: custom key the redactor doesn't recognize
fields = {"category": "application", "user_email": "john@example.com"}
```

### ✅ Correct: Use standard field names that trigger redaction

```python
# Good: "email" is masked automatically by the redaction layer
fields = {"category": "application", "email": "john@example.com"}
```

## Testing

```python
# tests/unit/adapters/logging/test_schema.py
from hermes_attractor.adapters.logging.schema import BaseLogFields


def test_base_fields_accepts_minimal_entry():
    fields: BaseLogFields = {"category": "application"}
    assert fields["category"] == "application"


def test_base_fields_allows_optional_duration():
    fields: BaseLogFields = {"category": "infrastructure", "duration_ms": 12.5}
    assert fields["duration_ms"] == 12.5
```

## Related References

- [event-naming.md](./event-naming.md) - Event naming conventions for the `event` field
- [safe-logger.md](./safe-logger.md) - Using `BaseLogFields` with the formatter
