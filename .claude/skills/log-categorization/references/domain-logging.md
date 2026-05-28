# Domain Logging

**Purpose**: Guidance for logging business-significant events within domain entities and services

## When to Use

When logging events from domain entities, value objects, domain services, or domain events. Use domain logs to capture what happened in business terms that stakeholders would understand.

Pass a small logging `Protocol` into domain methods rather than importing the logging adapter directly — this keeps the domain layer free of infrastructure dependencies.

## Pattern

```python
# src/hermes_attractor/domain/task.py
from __future__ import annotations

from typing import Any, Protocol


class DomainLogger(Protocol):
    def info(self, msg: str, *, extra: dict[str, Any]) -> None: ...
    def warning(self, msg: str, *, extra: dict[str, Any]) -> None: ...
    def error(self, msg: str, *, extra: dict[str, Any]) -> None: ...


class Task:
    def complete(self, logger: DomainLogger) -> None:
        if self.status is TaskStatus.COMPLETED:
            logger.warning(
                "already completed",
                extra={"event": "task.complete.already_completed",
                       "fields": {"category": "domain", "aggregate_type": "Task",
                                  "aggregate_id": self.id, "domain_event": "TaskCompletionAttempted"}},
            )
            return

        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now(UTC)

        logger.info(
            "task completed",
            extra={"event": "task.completed",
                   "fields": {"category": "domain", "aggregate_type": "Task",
                              "aggregate_id": self.id, "domain_event": "TaskCompleted",
                              "task_title": self.title,  # safe to log
                              "days_to_complete": self._days_to_complete()}},
        )

    def _days_to_complete(self) -> int:
        if self.completed_at is None or self.created_at is None:
            return 0
        return (self.completed_at - self.created_at).days
```

## Required Fields

Domain logs **must** include (inside `fields`):

- `category: "domain"`
- `aggregate_type`: The entity type (e.g. "Task", "User", "Order")
- `aggregate_id`: The entity identifier
- `domain_event`: The domain event name (e.g. "TaskCompleted", "UserRegistered")

And the top-level `event`: dot-notation event name (e.g. "task.completed").

## Characteristics

Domain logs should:

- Describe **what happened** in business terms
- Be understandable by non-technical stakeholders
- Never include technical implementation details
- Focus on state changes and business rules
- Include only safe-to-log business data

## Example Usage

```python
# src/hermes_attractor/domain/order.py
class Order:
    def cancel(self, reason: str, logger: DomainLogger) -> None:
        if self.status is OrderStatus.SHIPPED:
            logger.warning(
                "cannot cancel shipped",
                extra={"event": "order.cancel.cannot_cancel_shipped",
                       "fields": {"category": "domain", "aggregate_type": "Order",
                                  "aggregate_id": self.id, "domain_event": "OrderCancellationDenied",
                                  "order_status": self.status.value, "reason": reason}},
            )
            msg = "Cannot cancel shipped order"
            raise CannotCancelOrderError(msg)

        self.status = OrderStatus.CANCELLED

        logger.info(
            "order cancelled",
            extra={"event": "order.cancelled",
                   "fields": {"category": "domain", "aggregate_type": "Order",
                              "aggregate_id": self.id, "domain_event": "OrderCancelled",
                              "reason": reason, "order_total": self.total, "item_count": len(self.items)}},
        )
```

## Common Mistakes

### ❌ Mistake: Including technical details

```python
logger.info(
    "task completed",
    extra={"event": "task.completed",
           "fields": {"category": "domain", "aggregate_type": "Task", "aggregate_id": self.id,
                      "database_connection_time": 45,  # technical detail!
                      "cache_hit": True}},              # infrastructure detail!
)
```

### ✅ Correct: Pure business data

```python
logger.info(
    "task completed",
    extra={"event": "task.completed",
           "fields": {"category": "domain", "aggregate_type": "Task", "aggregate_id": self.id,
                      "domain_event": "TaskCompleted", "task_priority": self.priority,
                      "days_to_complete": self._days_to_complete()}},
)
```

### ❌ Mistake: Logging HTTP context

```python
logger.info(
    "task completed",
    extra={"event": "task.completed",
           "fields": {"category": "domain", "http_method": "POST", "http_status": 200}},  # wrong layer!
)
```

### ✅ Correct: Domain context only

```python
logger.info(
    "task completed",
    extra={"event": "task.completed",
           "fields": {"category": "domain", "aggregate_type": "Task",
                      "aggregate_id": self.id, "domain_event": "TaskCompleted"}},
)
```

## Testing

```python
# tests/unit/domain/test_task.py
from unittest.mock import MagicMock


def test_logs_domain_event_when_task_completed():
    logger = MagicMock()
    task = Task(id="task-1", title="Test task", status=TaskStatus.IN_PROGRESS)

    task.complete(logger)

    logger.info.assert_called_once()
    _, kwargs = logger.info.call_args
    fields = kwargs["extra"]["fields"]
    assert kwargs["extra"]["event"] == "task.completed"
    assert fields["category"] == "domain"
    assert fields["aggregate_type"] == "Task"
    assert fields["domain_event"] == "TaskCompleted"


def test_logs_warning_when_completing_already_completed_task():
    logger = MagicMock()
    task = Task(id="task-1", title="Test task", status=TaskStatus.COMPLETED)

    task.complete(logger)

    logger.warning.assert_called_once()
    _, kwargs = logger.warning.call_args
    assert kwargs["extra"]["event"] == "task.complete.already_completed"
    assert kwargs["extra"]["fields"]["category"] == "domain"
```

## Related References

- [decision-matrix.md](./decision-matrix.md) - Determine if a log belongs to the domain category
- [application-logging.md](./application-logging.md) - Log request flow and use case execution
