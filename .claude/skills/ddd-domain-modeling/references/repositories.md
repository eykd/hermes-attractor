# Repository Interfaces

Repository interfaces define the contract for persistence as **ports**.
Implementation lives in adapters. In the hermes-attractor layout, the port
(`typing.Protocol`) lives in `src/hermes_attractor/ports/` and the concrete
adapter lives in `src/hermes_attractor/adapters/`.

## Table of Contents
- [The Ports and Adapters Pattern](#the-ports-and-adapters-pattern)
- [Interface Design](#interface-design)
- [Common Repository Methods](#common-repository-methods)
- [Specification Pattern](#specification-pattern)
- [Implementation Guidelines](#implementation-guidelines)

## The Ports and Adapters Pattern

```
┌─────────────────────────────────────────────────────┐
│                   ports/ layer                       │
│  ┌─────────────────────────────────────────────┐    │
│  │  class TaskRepository(Protocol)  (PORT)      │    │
│  │    def find_by_id(id: UUID) -> Task | None   │    │
│  │    def save(task: Task) -> None              │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                         ▲
                         │ implements (structurally)
┌─────────────────────────────────────────────────────┐
│                  adapters/ layer                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  class SqliteTaskRepository  (ADAPTER)       │    │
│  │    def __init__(conn: sqlite3.Connection)    │    │
│  │    def find_by_id(id) -> Task | None         │    │
│  │    def save(task) -> None                    │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Key Rule**: The ports layer defines the interface. The adapters layer provides
the implementation. Because `Protocol` uses structural typing, adapters do not
need to inherit from the port — they just need matching method signatures.

## Interface Design

### Basic Repository Interface

```python
# src/hermes_attractor/ports/task_repository.py
from typing import Protocol
from uuid import UUID

from hermes_attractor.domain.entities import Task


class TaskRepository(Protocol):
    def find_by_id(self, task_id: UUID) -> Task | None: ...
    def find_all(self) -> list[Task]: ...
    def save(self, task: Task) -> None: ...
    def delete(self, task_id: UUID) -> None: ...
```

### Repository with Query Methods

```python
# src/hermes_attractor/ports/order_repository.py
from typing import Protocol
from uuid import UUID

from hermes_attractor.domain.entities import Order
from hermes_attractor.domain.value_objects import DateRange, OrderStatus


class OrderRepository(Protocol):
    # Core CRUD
    def find_by_id(self, order_id: UUID) -> Order | None: ...
    def save(self, order: Order) -> None: ...
    def delete(self, order_id: UUID) -> None: ...

    # Domain-specific queries
    def find_by_customer_id(self, customer_id: UUID) -> list[Order]: ...
    def find_by_status(self, status: OrderStatus) -> list[Order]: ...
    def find_by_date_range(self, date_range: DateRange) -> list[Order]: ...

    # Aggregate queries
    def count_by_status(self, status: OrderStatus) -> int: ...
    def exists_by_id(self, order_id: UUID) -> bool: ...
```

### Repository with Pagination

```python
from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar
from uuid import UUID

from hermes_attractor.domain.entities import Product

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total

    @property
    def has_previous(self) -> bool:
        return self.page > 1


@dataclass(frozen=True)
class PageRequest:
    page: int
    page_size: int
    sort_by: str | None = None
    sort_order: Literal["asc", "desc"] = "asc"


class ProductRepository(Protocol):
    def find_by_id(self, product_id: UUID) -> Product | None: ...
    def save(self, product: Product) -> None: ...

    # Paginated queries
    def find_all(self, page_request: PageRequest) -> Page[Product]: ...
    def find_by_category(
        self, category_id: UUID, page_request: PageRequest
    ) -> Page[Product]: ...
    def search(self, query: str, page_request: PageRequest) -> Page[Product]: ...
```

## Common Repository Methods

| Method | Purpose | Returns |
|--------|---------|---------|
| `find_by_id(id)` | Get single entity | `Entity \| None` |
| `find_all()` | Get all entities | `list[Entity]` |
| `save(entity)` | Insert or update | `None` |
| `delete(id)` | Remove entity | `None` |
| `exists_by_id(id)` | Check existence | `bool` |
| `count()` | Total count | `int` |

### Naming Conventions

```python
# Query methods start with "find_"
def find_by_id(self, task_id: UUID) -> Task | None: ...
def find_by_user_id(self, user_id: UUID) -> list[Task]: ...
def find_by_status(self, status: TaskStatus) -> list[Task]: ...
def find_completed_before(self, when: datetime) -> list[Task]: ...

# Boolean checks use "exists_" or "is_"
def exists_by_id(self, task_id: UUID) -> bool: ...
def exists_by_email(self, email: Email) -> bool: ...

# Counts use "count"
def count(self) -> int: ...
def count_by_status(self, status: TaskStatus) -> int: ...
```

## Specification Pattern

For complex queries, define specifications in the domain:

```python
# src/hermes_attractor/domain/specifications.py
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from hermes_attractor.domain.entities import Task


class TaskSpecification(Protocol):
    def is_satisfied_by(self, task: Task) -> bool: ...


@dataclass(frozen=True)
class OverdueTaskSpecification:
    now: datetime = datetime.now(timezone.utc)

    def is_satisfied_by(self, task: Task) -> bool:
        return task.due_date < self.now and not task.is_completed


# The port can accept a specification
class TaskRepository(Protocol):
    def find_by_id(self, task_id: UUID) -> Task | None: ...
    def find_all(self) -> list[Task]: ...
    def find_matching(self, spec: TaskSpecification) -> list[Task]: ...
    def save(self, task: Task) -> None: ...
```

## Implementation Guidelines

### Adapter Implementation

The adapter translates between domain entities and the storage representation.
It lives in `src/hermes_attractor/adapters/`.

```python
# src/hermes_attractor/adapters/sqlite_task_repository.py
import sqlite3
from uuid import UUID

from hermes_attractor.domain.entities import Task
from hermes_attractor.domain.value_objects import TaskStatus


class SqliteTaskRepository:
    """Structurally satisfies the TaskRepository port."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def find_by_id(self, task_id: UUID) -> Task | None:
        cursor = self._conn.execute(
            "SELECT id, user_id, title, completed, created_at "
            "FROM tasks WHERE id = ?",
            (str(task_id),),
        )
        row = cursor.fetchone()
        return self._to_domain(row) if row is not None else None

    def find_all(self) -> list[Task]:
        cursor = self._conn.execute(
            "SELECT id, user_id, title, completed, created_at "
            "FROM tasks ORDER BY created_at DESC"
        )
        return [self._to_domain(row) for row in cursor.fetchall()]

    def save(self, task: Task) -> None:
        self._conn.execute(
            """
            INSERT INTO tasks (id, user_id, title, completed, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                completed = excluded.completed
            """,
            (
                str(task.id),
                str(task.user_id),
                task.title,
                int(task.is_completed),
                task.created_at.isoformat(),
            ),
        )

    def delete(self, task_id: UUID) -> None:
        self._conn.execute("DELETE FROM tasks WHERE id = ?", (str(task_id),))

    def _to_domain(self, row: sqlite3.Row) -> Task:
        return Task.reconstitute(
            id=UUID(row["id"]),
            user_id=UUID(row["user_id"]),
            title=row["title"],
            status=(
                TaskStatus.COMPLETED if row["completed"] else TaskStatus.PENDING
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
```

### Unit of Work (Optional)

For transactional consistency across multiple repositories, define the port in
`ports/` and implement it in `adapters/`:

```python
# src/hermes_attractor/ports/unit_of_work.py
from types import TracebackType
from typing import Protocol

from hermes_attractor.ports.task_repository import TaskRepository
from hermes_attractor.ports.user_repository import UserRepository


class UnitOfWork(Protocol):
    tasks: TaskRepository
    users: UserRepository

    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


# Usage in a use case (context manager handles rollback on error)
def execute(self, request: CreateOrderRequest) -> None:
    with self._unit_of_work() as uow:
        user = uow.users.find_by_id(request.user_id)
        order = Order.create(customer_id=user.id)
        uow.orders.save(order)
        uow.commit()
```

### Testing with the Repository Port

Use an in-memory fake that structurally satisfies the port — no mocks needed.

```python
from uuid import UUID

from hermes_attractor.domain.entities import Task


class InMemoryTaskRepository:
    """Satisfies the TaskRepository port for fast, isolated tests."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, Task] = {}

    def find_by_id(self, task_id: UUID) -> Task | None:
        return self._tasks.get(task_id)

    def find_all(self) -> list[Task]:
        return list(self._tasks.values())

    def save(self, task: Task) -> None:
        self._tasks[task.id] = task

    def delete(self, task_id: UUID) -> None:
        self._tasks.pop(task_id, None)


# Use case test
class TestCreateTask:
    def test_creates_and_persists_task(self) -> None:
        repository = InMemoryTaskRepository()
        use_case = CreateTask(repository)

        result = use_case.execute(user_id=uuid4(), title="Test")

        saved = repository.find_by_id(result.id)
        assert saved is not None
        assert saved.title == "Test"
```
