# Logger Factory

**Purpose**: Logger factory with environment-aware configuration and category-specific variants.

## When to Use

Use this reference when implementing logger creation that wires the `JsonFormatter` and `SafeLoggerAdapter`, pulls operation context from `contextvars`, and provides specialized helpers for the domain/application/infrastructure layers.

Loggers are named after the layer (`hermes_attractor.domain`, `hermes_attractor.use_cases`, `hermes_attractor.adapters`) so that standard `logging` configuration and filtering apply per layer.

## Pattern

```python
# src/hermes_attractor/adapters/logging/__init__.py
from __future__ import annotations

import logging
from functools import lru_cache

from hermes_attractor.adapters.logging.safe_logger import JsonFormatter, SafeLoggerAdapter

_DOMAIN_LOGGER = "hermes_attractor.domain"
_APPLICATION_LOGGER = "hermes_attractor.use_cases"
_INFRA_LOGGER = "hermes_attractor.adapters"


@lru_cache(maxsize=None)
def _configure(name: str, service: str, environment: str, version: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO if environment == "production" else logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter(service, environment=environment, version=version))
        logger.addHandler(handler)
        logger.propagate = False
    return logger


def create_logger(*, service: str, environment: str, version: str,
                   name: str = _APPLICATION_LOGGER) -> SafeLoggerAdapter:
    logger = _configure(name, service, environment, version)
    return SafeLoggerAdapter(logger, is_production=environment == "production")


def create_domain_logger(*, service: str, environment: str, version: str) -> SafeLoggerAdapter:
    return create_logger(service=service, environment=environment, version=version, name=_DOMAIN_LOGGER)


def create_application_logger(*, service: str, environment: str, version: str) -> SafeLoggerAdapter:
    return create_logger(service=service, environment=environment, version=version, name=_APPLICATION_LOGGER)


def create_infra_logger(*, service: str, environment: str, version: str) -> SafeLoggerAdapter:
    return create_logger(service=service, environment=environment, version=version, name=_INFRA_LOGGER)
```

Set `category` once per layer by convention (pass it in `fields`), or wrap the adapter to inject it automatically.

## Decision Matrix

| Usage Context              | Factory Function            | Logger Name                   | Debug Logs? |
| -------------------------- | --------------------------- | ----------------------------- | ----------- |
| Domain entities/services   | `create_domain_logger()`    | `hermes_attractor.domain`     | No (prod)   |
| Use cases                  | `create_application_logger()` | `hermes_attractor.use_cases`  | No (prod)   |
| Adapters/repositories      | `create_infra_logger()`     | `hermes_attractor.adapters`   | Yes (dev)   |
| Generic logging            | `create_logger()`           | `hermes_attractor.use_cases`  | No (prod)   |

## Example Usage

### Domain Layer

```python
# src/hermes_attractor/domain/task.py
from hermes_attractor.adapters.logging import create_domain_logger


class Task:
    def complete(self, *, service: str, environment: str, version: str) -> None:
        logger = create_domain_logger(service=service, environment=environment, version=version)

        if self.status is TaskStatus.COMPLETED:
            logger.warning(
                "already completed",
                extra={"event": "task.complete.already_completed",
                       "fields": {"category": "domain", "aggregate_type": "Task", "aggregate_id": self.id}},
            )
            return

        self.status = TaskStatus.COMPLETED

        logger.info(
            "task completed",
            extra={"event": "task.completed",
                   "fields": {"category": "domain", "aggregate_type": "Task",
                              "aggregate_id": self.id, "domain_event": "TaskCompleted"}},
        )
```

### Application Layer

```python
# src/hermes_attractor/use_cases/complete_task.py
from time import monotonic

from hermes_attractor.adapters.logging import create_application_logger


class CompleteTaskUseCase:
    def __init__(self, *, service: str, environment: str, version: str) -> None:
        self._log_opts = {"service": service, "environment": environment, "version": version}

    def execute(self, request: CompleteTaskRequest) -> CompleteTaskResponse:
        logger = create_application_logger(**self._log_opts)
        start = monotonic()

        logger.info(
            "complete task started",
            extra={"event": "use_case.complete_task.started",
                   "fields": {"category": "application", "task_id": request.task_id,
                              "user_id": request.user_id}},
        )

        try:
            result = self._process(request)
            logger.info(
                "complete task succeeded",
                extra={"event": "use_case.complete_task.succeeded",
                       "fields": {"category": "application", "task_id": request.task_id,
                                  "duration_ms": round((monotonic() - start) * 1000)}},
            )
            return result
        except Exception as exc:
            logger.error(
                "complete task failed",
                extra={"event": "use_case.complete_task.failed",
                       "fields": {"category": "application", "task_id": request.task_id,
                                  "error_type": type(exc).__name__,
                                  "duration_ms": round((monotonic() - start) * 1000)}},
            )
            raise
```

### Infrastructure Layer

```python
# src/hermes_attractor/adapters/sqlite_task_repository.py
from time import monotonic

from hermes_attractor.adapters.logging import create_infra_logger


class SqliteTaskRepository:
    def __init__(self, connection, *, service: str, environment: str, version: str) -> None:
        self._conn = connection
        self._log_opts = {"service": service, "environment": environment, "version": version}

    def find_by_id(self, task_id: str) -> Task | None:
        logger = create_infra_logger(**self._log_opts)
        start = monotonic()

        logger.debug(
            "query started",
            extra={"event": "db.query.started",
                   "fields": {"category": "infrastructure", "query_type": "SELECT",
                              "table": "tasks", "operation": "find_by_id"}},
        )

        try:
            row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            logger.info(
                "query result",
                extra={"event": "db.query.succeeded" if row else "db.query.not_found",
                       "fields": {"category": "infrastructure", "query_type": "SELECT",
                                  "table": "tasks", "duration_ms": round((monotonic() - start) * 1000)}},
            )
            return self._map(row) if row else None
        except Exception as exc:
            logger.error(
                "query failed",
                extra={"event": "db.query.failed",
                       "fields": {"category": "infrastructure", "query_type": "SELECT",
                                  "table": "tasks", "error_type": type(exc).__name__,
                                  "duration_ms": round((monotonic() - start) * 1000)}},
            )
            raise
```

## Edge Cases

### Missing Operation Context

**Scenario**: Logger used outside an operation context (e.g. a scheduled job).
**Solution**: The formatter falls back to `request_id = "no-context"`; no special handling needed at the call site.

### Dynamic Environment Configuration

**Scenario**: Environment and version are not known at import time.
**Solution**: Pass them when constructing the use case / adapter, and create the logger at call time.

```python
use_case = CompleteTaskUseCase(service="task-api", environment=settings.environment, version=settings.version)
```

## Common Mistakes

### ❌ Mistake: Creating the logger at module scope

A logger created at import time captures no operation context (and `lru_cache` on `_configure` only caches handler wiring, not context).

```python
# Bad: created before any context is bound
logger = create_logger(service="api", environment="prod", version="1.0.0")

def handle_request() -> Response:
    logger.info("received", extra={"event": "request.received", "fields": {"category": "application"}})
    # request_id is whatever is bound *at log time*; if module-scope code logs, it's "no-context"
```

### ✅ Correct: Create/log within the operation scope

```python
# Good: logger used inside run_with_context, so request_id is correct
def handle_request() -> Response:
    with run_with_context(OperationContext(request_id=generate_request_id())):
        logger = create_logger(service="api", environment="prod", version="1.0.0")
        logger.info("received", extra={"event": "request.received", "fields": {"category": "application"}})
```

### ❌ Mistake: Re-adding handlers on every call

Configuring handlers each time a logger is created duplicates log lines.

```python
# Bad: adds a new StreamHandler every call → duplicate output
logger = logging.getLogger("hermes_attractor.use_cases")
logger.addHandler(logging.StreamHandler())
```

### ✅ Correct: Configure handlers once

```python
# Good: guard with `if not logger.handlers` (as in _configure above)
if not logger.handlers:
    logger.addHandler(handler)
```

## Testing

```python
# tests/unit/adapters/logging/test_logger_factory.py
import json
import logging

from hermes_attractor.adapters.logging import create_domain_logger, create_logger
from hermes_attractor.adapters.logging.context import (
    OperationContext,
    generate_request_id,
    run_with_context,
)


def test_logger_includes_request_id(capsys):
    request_id = generate_request_id()
    with run_with_context(OperationContext(request_id=request_id)):
        logger = create_logger(service="test", environment="test", version="1.0.0")
        logger.info("event", extra={"event": "test.event", "fields": {"category": "application"}})

    line = capsys.readouterr().err.strip().splitlines()[-1]
    assert json.loads(line)["request_id"] == request_id


def test_logger_uses_fallback_request_id(capsys):
    logger = create_logger(service="test", environment="test", version="1.0.0")
    logger.info("event", extra={"event": "test.event", "fields": {"category": "application"}})

    line = capsys.readouterr().err.strip().splitlines()[-1]
    assert json.loads(line)["request_id"] == "no-context"


def test_production_suppresses_debug(capsys):
    logger = create_logger(service="test", environment="production", version="1.0.0")
    logger.debug("event", extra={"event": "debug.event", "fields": {"category": "application"}})

    assert capsys.readouterr().err.strip() == ""
```

## Related References

- [safe-logger.md](./safe-logger.md) - `JsonFormatter` and `SafeLoggerAdapter` used by the factory
- [context-management.md](./context-management.md) - `get_context()` for operation correlation
- [base-fields.md](./base-fields.md) - `BaseLogFields` structure
