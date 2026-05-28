# Infrastructure Logging

**Purpose**: Guidance for logging interactions with external systems and infrastructure components

## When to Use

When logging from repository/adapter implementations, cache adapters, external API clients, or any infrastructure component that interacts with databases, storage, or external services. Use infrastructure logs to track system health and performance.

## Pattern

```python
# src/hermes_attractor/adapters/sqlite_task_repository.py
from __future__ import annotations

from time import monotonic
from typing import Any, Protocol


class InfrastructureLogger(Protocol):
    def debug(self, msg: str, *, extra: dict[str, Any]) -> None: ...
    def info(self, msg: str, *, extra: dict[str, Any]) -> None: ...
    def warning(self, msg: str, *, extra: dict[str, Any]) -> None: ...
    def error(self, msg: str, *, extra: dict[str, Any]) -> None: ...


class SqliteTaskRepository:
    def __init__(self, connection) -> None:
        self._conn = connection

    def find_by_id(self, task_id: str, logger: InfrastructureLogger) -> Task | None:
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
                                  "table": "tasks", "operation": "find_by_id",
                                  "duration_ms": round((monotonic() - start) * 1000),
                                  "row_count": 1 if row else 0}},
            )
            return self._map(row) if row else None
        except Exception as exc:
            logger.error(
                "query failed",
                extra={"event": "db.query.failed",
                       "fields": {"category": "infrastructure", "query_type": "SELECT",
                                  "table": "tasks", "operation": "find_by_id",
                                  "duration_ms": round((monotonic() - start) * 1000),
                                  "error_type": type(exc).__name__}},
            )
            raise
```

## Required Fields

Infrastructure logs **should** include (inside `fields`):

- `category: "infrastructure"`
- `duration_ms`: operation timing for performance monitoring
- Operation context: `query_type`, `table`, `operation`, etc.

And the top-level `event`: dot-notation event name (e.g. "db.query.succeeded").

## Characteristics

Infrastructure logs should:

- Track timing information for performance monitoring
- Include operation metadata without sensitive data
- Capture connection states and retry attempts
- Enable infrastructure health monitoring
- Never include query parameters that might contain PII

## Example Usage

### Database Repository (write)

```python
class SqliteTaskRepository:
    def save(self, task: Task, logger: InfrastructureLogger) -> None:
        start = monotonic()

        logger.debug(
            "query started",
            extra={"event": "db.query.started",
                   "fields": {"category": "infrastructure", "query_type": "INSERT",
                              "table": "tasks", "operation": "save"}},
        )

        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO tasks (id, title, status, created_at) VALUES (?, ?, ?, ?)",
                (task.id, task.title, task.status.value, task.created_at.isoformat()),
            )
            logger.info(
                "query succeeded",
                extra={"event": "db.query.succeeded",
                       "fields": {"category": "infrastructure", "query_type": "INSERT",
                                  "table": "tasks", "operation": "save",
                                  "duration_ms": round((monotonic() - start) * 1000)}},
            )
        except Exception as exc:
            logger.error(
                "query failed",
                extra={"event": "db.query.failed",
                       "fields": {"category": "infrastructure", "query_type": "INSERT",
                                  "table": "tasks", "operation": "save",
                                  "duration_ms": round((monotonic() - start) * 1000),
                                  "error_type": type(exc).__name__}},
            )
            raise
```

### Cache Adapter

```python
class CacheAdapter:
    def get(self, key: str, logger: InfrastructureLogger) -> object | None:
        start = monotonic()
        try:
            value = self._backend.get(key)
            logger.info(
                "cache lookup",
                extra={"event": "cache.hit" if value is not None else "cache.miss",
                       "fields": {"category": "infrastructure", "operation": "get",
                                  "key_prefix": key.split(":")[0],  # prefix only, never the full key
                                  "duration_ms": round((monotonic() - start) * 1000)}},
            )
            return value
        except Exception as exc:
            logger.error(
                "cache error",
                extra={"event": "cache.error",
                       "fields": {"category": "infrastructure", "operation": "get",
                                  "key_prefix": key.split(":")[0],
                                  "duration_ms": round((monotonic() - start) * 1000),
                                  "error_type": type(exc).__name__}},
            )
            return None  # degrade gracefully
```

### External API Client

```python
import httpx


class PaymentGatewayClient:
    def __init__(self, client: httpx.Client, api_key: str) -> None:
        self._client = client
        self._api_key = api_key

    def charge(self, amount: int, currency: str, logger: InfrastructureLogger) -> str:
        start = monotonic()

        logger.info(
            "request started",
            extra={"event": "external_api.request.started",
                   "fields": {"category": "infrastructure", "service": "payment_gateway",
                              "endpoint": "/charges", "http_method": "POST"}},
        )

        try:
            response = self._client.post(
                "https://api.payment-gateway.com/charges",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"amount": amount, "currency": currency},
            )
            duration_ms = round((monotonic() - start) * 1000)

            if response.status_code >= 400:
                logger.warning(
                    "request failed",
                    extra={"event": "external_api.request.failed",
                           "fields": {"category": "infrastructure", "service": "payment_gateway",
                                      "endpoint": "/charges", "http_method": "POST",
                                      "http_status": response.status_code, "duration_ms": duration_ms}},
                )
                msg = f"Payment gateway returned {response.status_code}"
                raise PaymentGatewayError(msg)

            logger.info(
                "request succeeded",
                extra={"event": "external_api.request.succeeded",
                       "fields": {"category": "infrastructure", "service": "payment_gateway",
                                  "endpoint": "/charges", "http_method": "POST",
                                  "http_status": response.status_code, "duration_ms": duration_ms}},
            )
            return response.json()["transaction_id"]
        except httpx.HTTPError as exc:
            logger.error(
                "request failed",
                extra={"event": "external_api.request.failed",
                       "fields": {"category": "infrastructure", "service": "payment_gateway",
                                  "endpoint": "/charges", "http_method": "POST",
                                  "duration_ms": round((monotonic() - start) * 1000),
                                  "error_type": type(exc).__name__}},
            )
            raise
```

## Common Mistakes

### ❌ Mistake: Logging business logic

```python
logger.info(
    "query succeeded",
    extra={"event": "db.query.succeeded",
           "fields": {"category": "infrastructure", "task_completed": True,  # business logic!
                      "domain_event": "TaskCompleted"}},                     # domain concern!
)
```

### ✅ Correct: Focus on infrastructure concerns

```python
logger.info(
    "query succeeded",
    extra={"event": "db.query.succeeded",
           "fields": {"category": "infrastructure", "query_type": "UPDATE",
                      "table": "tasks", "duration_ms": 15, "row_count": 1}},
)
```

### ❌ Mistake: Logging sensitive query parameters

```python
logger.debug(
    "query started",
    extra={"event": "db.query.started",
           "fields": {"category": "infrastructure",
                      "query": "SELECT * FROM users WHERE email = ?",
                      "parameters": ["user@example.com"]}},  # PII!
)
```

### ✅ Correct: Log the query shape without parameters

```python
logger.debug(
    "query started",
    extra={"event": "db.query.started",
           "fields": {"category": "infrastructure", "query_type": "SELECT",
                      "table": "users", "operation": "find_by_email"}},  # no parameters
)
```

## Testing

```python
# tests/unit/adapters/test_sqlite_task_repository.py
from unittest.mock import MagicMock

import pytest


def test_logs_query_lifecycle_with_timing():
    logger = MagicMock()
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"id": "task-1", "title": "Test"}
    repository = SqliteTaskRepository(conn)

    repository.find_by_id("task-1", logger)

    assert logger.debug.call_args.kwargs["extra"]["event"] == "db.query.started"
    info_fields = logger.info.call_args.kwargs["extra"]["fields"]
    assert info_fields["category"] == "infrastructure"
    assert "duration_ms" in info_fields
    assert info_fields["row_count"] == 1


def test_logs_error_with_duration_when_query_fails():
    logger = MagicMock()
    conn = MagicMock()
    conn.execute.side_effect = RuntimeError("Database error")
    repository = SqliteTaskRepository(conn)

    with pytest.raises(RuntimeError):
        repository.find_by_id("task-1", logger)

    extra = logger.error.call_args.kwargs["extra"]
    assert extra["event"] == "db.query.failed"
    assert extra["fields"]["error_type"] == "RuntimeError"
    assert "duration_ms" in extra["fields"]
```

## Related References

- [decision-matrix.md](./decision-matrix.md) - Determine if a log belongs to the infrastructure category
- [application-logging.md](./application-logging.md) - Log use case orchestration
- [domain-logging.md](./domain-logging.md) - Log business events
