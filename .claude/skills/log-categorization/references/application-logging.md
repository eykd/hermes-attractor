# Application Logging

**Purpose**: Guidance for logging request flow, validation, and use case execution in the application layer

## When to Use

When logging from request handlers, use cases, middleware, or application services. Use application logs to track how requests flow through the system and how business operations are orchestrated.

## Pattern

```python
# src/hermes_attractor/use_cases/complete_task.py
from __future__ import annotations

from time import monotonic
from typing import Any, Protocol


class ApplicationLogger(Protocol):
    def info(self, msg: str, *, extra: dict[str, Any]) -> None: ...
    def warning(self, msg: str, *, extra: dict[str, Any]) -> None: ...
    def error(self, msg: str, *, extra: dict[str, Any]) -> None: ...


class CompleteTaskUseCase:
    def __init__(self, task_repository: TaskRepository) -> None:
        self._task_repository = task_repository

    def execute(self, request: CompleteTaskRequest, logger: ApplicationLogger) -> CompleteTaskResponse:
        start = monotonic()

        logger.info(
            "started",
            extra={"event": "use_case.complete_task.started",
                   "fields": {"category": "application", "task_id": request.task_id,
                              "user_id": request.user_id}},
        )

        try:
            task = self._task_repository.find_by_id(request.task_id)
            if task is None:
                logger.warning(
                    "task not found",
                    extra={"event": "use_case.complete_task.task_not_found",
                           "fields": {"category": "application", "task_id": request.task_id,
                                      "user_id": request.user_id}},
                )
                return CompleteTaskResponse(success=False, error="TASK_NOT_FOUND")

            task.complete(logger)  # domain log emitted from the entity
            self._task_repository.save(task)

            logger.info(
                "succeeded",
                extra={"event": "use_case.complete_task.succeeded",
                       "fields": {"category": "application", "task_id": request.task_id,
                                  "user_id": request.user_id,
                                  "duration_ms": round((monotonic() - start) * 1000)}},
            )
            return CompleteTaskResponse(success=True)
        except Exception as exc:
            logger.error(
                "failed",
                extra={"event": "use_case.complete_task.failed",
                       "fields": {"category": "application", "task_id": request.task_id,
                                  "user_id": request.user_id, "error_type": type(exc).__name__,
                                  "error_message": str(exc),
                                  "duration_ms": round((monotonic() - start) * 1000)}},
            )
            raise
```

## Required Fields

Application logs **should** include (inside `fields`):

- `category: "application"`
- `duration_ms`: operation timing when the operation completes
- HTTP context when relevant: `http_method`, `http_path`, `http_status`

And the top-level `event`: dot-notation event name (e.g. "use_case.complete_task.started").

## Characteristics

Application logs should:

- Track request flow through the system
- Include timing information for performance monitoring
- Capture validation failures and business rule violations
- Bridge between external requests and domain operations
- Include user context for authorization tracking

## Example Usage

### Request Handler

```python
# src/hermes_attractor/adapters/task_handler.py
from time import monotonic


def handle_complete_task(request: Request, logger: ApplicationLogger) -> Response:
    start = monotonic()

    logger.info(
        "request received",
        extra={"event": "http.request.received",
               "fields": {"category": "application", "http_method": request.method,
                          "http_path": request.path}},
    )

    try:
        result = CompleteTaskUseCase(repository).execute(
            CompleteTaskRequest(task_id=request.json["task_id"], user_id="user-123"), logger,
        )
        status = 200 if result.success else 404

        logger.info(
            "response sent",
            extra={"event": "http.response.sent",
                   "fields": {"category": "application", "http_method": request.method,
                              "http_path": request.path, "http_status": status,
                              "duration_ms": round((monotonic() - start) * 1000)}},
        )
        return Response.json(result, status=status)
    except Exception as exc:
        logger.error(
            "request failed",
            extra={"event": "http.request.failed",
                   "fields": {"category": "application", "http_method": request.method,
                              "http_path": request.path, "http_status": 500,
                              "error_message": str(exc),
                              "duration_ms": round((monotonic() - start) * 1000)}},
        )
        return Response.json({"error": "Internal Server Error"}, status=500)
```

### Validation Logging

```python
# src/hermes_attractor/use_cases/validators.py
class TaskValidator:
    def validate(self, request: CreateTaskRequest, logger: ApplicationLogger) -> ValidationResult:
        errors: list[str] = []
        if not request.title or len(request.title) < 3:
            errors.append("Title must be at least 3 characters")
        if request.title and len(request.title) > 200:
            errors.append("Title must be at most 200 characters")

        if errors:
            logger.warning(
                "validation failed",
                extra={"event": "validation.failed",
                       "fields": {"category": "application", "validator": "TaskValidator",
                                  "error_count": len(errors)}},  # don't log raw errors (may contain PII)
            )
            return ValidationResult(valid=False, errors=errors)

        return ValidationResult(valid=True, errors=[])
```

## Common Mistakes

### ❌ Mistake: Logging domain events at the application layer

```python
# Wrong: this is a domain event, logged as application
logger.info(
    "task completed",
    extra={"event": "task.completed",  # domain event!
           "fields": {"category": "application", "aggregate_type": "Task", "domain_event": "TaskCompleted"}},
)
```

### ✅ Correct: Separate domain and application events

```python
# Application log: orchestration
logger.info(
    "succeeded",
    extra={"event": "use_case.complete_task.succeeded",
           "fields": {"category": "application", "task_id": task_id, "duration_ms": 45}},
)

# Domain log: business event (emitted from the entity)
task.complete(logger)
```

### ❌ Mistake: Including infrastructure details

```python
logger.info(
    "succeeded",
    extra={"event": "use_case.complete_task.succeeded",
           "fields": {"category": "application", "database_query_time": 15, "cache_hit": True}},  # infra concerns!
)
```

### ✅ Correct: Focus on application concerns

```python
logger.info(
    "succeeded",
    extra={"event": "use_case.complete_task.succeeded",
           "fields": {"category": "application", "task_id": task_id, "user_id": user_id,
                      "duration_ms": round((monotonic() - start) * 1000)}},
)
```

## Testing

```python
# tests/unit/use_cases/test_complete_task.py
from unittest.mock import MagicMock

import pytest


def test_logs_use_case_lifecycle():
    logger = MagicMock()
    use_case = CompleteTaskUseCase(repository)

    use_case.execute(CompleteTaskRequest(task_id="task-1", user_id="user-1"), logger)

    events = [call.kwargs["extra"]["event"] for call in logger.info.call_args_list]
    assert "use_case.complete_task.started" in events
    assert "use_case.complete_task.succeeded" in events


def test_logs_warning_when_task_not_found():
    logger = MagicMock()
    repository = MagicMock()
    repository.find_by_id.return_value = None
    use_case = CompleteTaskUseCase(repository)

    result = use_case.execute(CompleteTaskRequest(task_id="task-1", user_id="user-1"), logger)

    logger.warning.assert_called_once()
    assert logger.warning.call_args.kwargs["extra"]["event"] == "use_case.complete_task.task_not_found"
    assert result.success is False


def test_logs_error_with_duration_on_exception():
    logger = MagicMock()
    repository = MagicMock()
    repository.find_by_id.side_effect = RuntimeError("Database error")
    use_case = CompleteTaskUseCase(repository)

    with pytest.raises(RuntimeError):
        use_case.execute(CompleteTaskRequest(task_id="task-1", user_id="user-1"), logger)

    fields = logger.error.call_args.kwargs["extra"]["fields"]
    assert fields["error_type"] == "RuntimeError"
    assert fields["error_message"] == "Database error"
    assert "duration_ms" in fields
```

## Related References

- [decision-matrix.md](./decision-matrix.md) - Determine if a log belongs to the application category
- [domain-logging.md](./domain-logging.md) - Log business events from domain entities
- [infrastructure-logging.md](./infrastructure-logging.md) - Log external system interactions
