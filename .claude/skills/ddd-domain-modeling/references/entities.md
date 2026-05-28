# Entities

Entities have identity that persists through state changes. In Python, model
them as a mutable `@dataclass` in `src/hermes_attractor/domain/entities.py`,
with equality based on `id` (not all attributes).

## Table of Contents
- [Structure](#structure)
- [Factory Methods](#factory-methods)
- [Invariant Enforcement](#invariant-enforcement)
- [Aggregate Roots](#aggregate-roots)
- [Testing Entities](#testing-entities)

## Structure

Use a private-by-convention constructor accessed through factories. Mark mutable
internal state with a leading underscore and expose read-only `@property`
accessors — never public setters.

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from hermes_attractor.domain.exceptions import ValidationError
from hermes_attractor.domain.value_objects import TaskStatus


@dataclass(eq=False)  # identity equality, not value equality
class Task:
    id: UUID
    user_id: UUID
    _title: str
    _status: TaskStatus
    created_at: datetime

    # Factory for new entities - validates business rules
    @classmethod
    def create(cls, user_id: UUID, title: str) -> "Task":
        if len(title.strip()) < 3:
            raise ValidationError("Title must be at least 3 characters")
        return cls(
            id=uuid4(),
            user_id=user_id,
            _title=title.strip(),
            _status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

    # Factory for reconstitution from persistence - no validation
    @classmethod
    def reconstitute(
        cls,
        *,
        id: UUID,
        user_id: UUID,
        title: str,
        status: TaskStatus,
        created_at: datetime,
    ) -> "Task":
        return cls(id, user_id, title, status, created_at)

    # Read-only accessors (never setters)
    @property
    def title(self) -> str:
        return self._title

    @property
    def is_completed(self) -> bool:
        return self._status.is_completed

    # Behavior methods enforce business rules
    def complete(self) -> None:
        if self._status.is_completed:
            raise ValidationError("Task already completed")
        self._status = TaskStatus.COMPLETED

    def rename(self, new_title: str) -> None:
        if len(new_title.strip()) < 3:
            raise ValidationError("Title must be at least 3 characters")
        self._title = new_title.strip()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Task) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)
```

## Factory Methods

Two factory methods serve different purposes:

| Method | Purpose | Validates | Generates ID |
|--------|---------|-----------|--------------|
| `create()` | New entities from input | Yes | Yes |
| `reconstitute()` | Rebuild from persistence | No | No |

```python
# Use case layer uses create()
task = Task.create(user_id=user_id, title="Buy milk")

# Repository adapter uses reconstitute()
def to_domain(self, row: TaskRow) -> Task:
    return Task.reconstitute(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        status=TaskStatus.COMPLETED if row.completed else TaskStatus.PENDING,
        created_at=row.created_at,
    )
```

## Invariant Enforcement

Invariants are rules that must **always** be true. Enforce them in
`__post_init__` (construction-time) and in behavior methods (mutation-time).

```python
from dataclasses import dataclass, field

from hermes_attractor.domain.exceptions import ValidationError


@dataclass(eq=False)
class Order:
    id: UUID
    _items: list["LineItem"] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Construction invariant
        if not self._items:
            raise ValidationError("Order must have at least one item")

    def add_item(self, item: "LineItem") -> None:
        # Mutation invariant: no duplicates
        if any(i.product_id == item.product_id for i in self._items):
            raise ValidationError("Product already in order")
        self._items.append(item)

    def remove_item(self, product_id: UUID) -> None:
        # Invariant: cannot remove the last item
        if len(self._items) == 1:
            raise ValidationError("Cannot remove last item from order")
        self._items = [i for i in self._items if i.product_id != product_id]
```

## Aggregate Roots

Aggregate roots control all access to their child entities. Expose children only
as a defensive, read-only copy; route all mutations through the root's methods.

```python
@dataclass(eq=False)
class Order:
    id: UUID
    currency: str
    _items: list["LineItem"] = field(default_factory=list)
    _total: "Money" = field(init=False)

    def __post_init__(self) -> None:
        self._recalculate_total()

    @property
    def items(self) -> tuple["LineItem", ...]:
        return tuple(self._items)  # defensive, immutable view

    @property
    def total(self) -> "Money":
        return self._total

    def add_item(self, product_id: UUID, quantity: int, price: "Money") -> None:
        self._items.append(LineItem.create(product_id, quantity, price))
        self._recalculate_total()

    def _recalculate_total(self) -> None:
        total = Money.zero(self.currency)
        for item in self._items:
            total = total.add(item.subtotal)
        self._total = total
```

## Testing Entities

Domain entities are pure — test without mocks.

```python
from uuid import uuid4

import pytest

from hermes_attractor.domain.entities import Task
from hermes_attractor.domain.exceptions import ValidationError


class TestTaskCreate:
    def test_creates_task_with_valid_title(self) -> None:
        task = Task.create(user_id=uuid4(), title="Buy milk")
        assert task.title == "Buy milk"
        assert task.is_completed is False
        assert task.id is not None

    def test_rejects_short_titles(self) -> None:
        with pytest.raises(ValidationError, match="at least 3 characters"):
            Task.create(user_id=uuid4(), title="ab")

    def test_trims_whitespace(self) -> None:
        task = Task.create(user_id=uuid4(), title="  Buy milk  ")
        assert task.title == "Buy milk"


class TestTaskComplete:
    def test_marks_pending_task_as_completed(self) -> None:
        task = Task.create(user_id=uuid4(), title="Test")
        task.complete()
        assert task.is_completed is True

    def test_raises_when_completing_twice(self) -> None:
        task = Task.create(user_id=uuid4(), title="Test")
        task.complete()
        with pytest.raises(ValidationError, match="already completed"):
            task.complete()
```
