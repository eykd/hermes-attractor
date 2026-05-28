---
name: structured-logging
description: "Use when: (1) Adding structured JSON logging with stdlib logging, (2) Setting up operation/request correlation via contextvars, (3) Defining a base-fields TypedDict schema or event-naming conventions, (4) Building a logger factory with environment-aware redaction."
---

# Structured Logging

**Use when:** Adding structured logging to a Python application with operation/request correlation and environment-aware redaction.

## Overview

This skill provides complete guidance on implementing structured logging in Python using the standard library `logging` module. It covers a JSON formatter with PII redaction, operation correlation using `contextvars`, a base-fields schema, event naming conventions, and logger factory patterns for domain/application/infrastructure layers.

The approach uses stdlib `logging` only — no hard third-party dependency. You attach structured fields via the `extra=` argument and a `LoggerAdapter`, and a custom `Formatter` serializes records to JSON. If you later adopt `structlog`, the same field schema and event names carry over.

## Decision Tree

### Need to format records as JSON with redaction?

**When**: Creating the core logging infrastructure (a `logging.Formatter` subclass with PII redaction)
**Go to**: [references/safe-logger.md](./references/safe-logger.md)

### Need to manage operation context?

**When**: Setting up `contextvars` for request/operation correlation and trace context
**Go to**: [references/context-management.md](./references/context-management.md)

### Need to define the log field schema?

**When**: Defining `BaseLogFields` (a `TypedDict`) and required fields per category
**Go to**: [references/base-fields.md](./references/base-fields.md)

### Need to name events?

**When**: Creating event naming conventions and categorizing logs
**Go to**: [references/event-naming.md](./references/event-naming.md)

### Need to create logger instances?

**When**: Building the logger factory with environment-aware configuration
**Go to**: [references/logger-factory.md](./references/logger-factory.md)

## Quick Example

```python
# src/hermes_attractor/adapters/logging/__init__.py
from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


class JsonFormatter(logging.Formatter):
    """Serialize each record to a single JSON line with correlation IDs."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": self._service,
            "request_id": _request_id.get() or "no-context",
            "event": getattr(record, "event", record.getMessage()),
        }
        if (trace_id := _trace_id.get()) is not None:
            payload["trace_id"] = trace_id
        # Merge structured fields passed via `extra=`.
        for key, value in getattr(record, "fields", {}).items():
            payload[key] = value
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """Return a layer-named logger, e.g. ``hermes_attractor.use_cases``."""
    return logging.getLogger(name)
```

```python
# Usage inside an operation
logger = get_logger("hermes_attractor.use_cases")
logger.info("use case complete", extra={"event": "use_case.create_user.succeeded",
                                         "fields": {"category": "application", "duration_ms": 45}})
```

## Cross-References

- **[log-categorization](../log-categorization/SKILL.md)**: Categorize logs by domain/application/infrastructure layers following Clean Architecture
- **[pii-redaction](../pii-redaction/SKILL.md)**: Implement systematic PII and secret redaction patterns for defense-in-depth data protection
- **[sentry-integration](../sentry-integration/SKILL.md)**: Optionally forward errors/breadcrumbs to Sentry while keeping structured-log correlation

## Reference Files

- [references/safe-logger.md](./references/safe-logger.md) - JSON `Formatter` and a redaction-aware `LoggerAdapter`
- [references/context-management.md](./references/context-management.md) - `contextvars` patterns for operation correlation
- [references/base-fields.md](./references/base-fields.md) - `BaseLogFields` schema and required fields by category
- [references/event-naming.md](./references/event-naming.md) - Event naming conventions and categorization rules
- [references/logger-factory.md](./references/logger-factory.md) - Logger factory with domain/application/infrastructure variants
