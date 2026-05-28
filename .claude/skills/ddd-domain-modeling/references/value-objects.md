# Value Objects

Value objects are immutable, defined by their attributes, and have no identity.
In Python, model them as `@dataclass(frozen=True)` in
`src/hermes_attractor/domain/value_objects.py`.

## Table of Contents
- [Characteristics](#characteristics)
- [Patterns](#patterns)
- [Common Value Objects](#common-value-objects)
- [Equality and Comparison](#equality-and-comparison)
- [Testing Value Objects](#testing-value-objects)

## Characteristics

| Characteristic | Description |
|---------------|-------------|
| Immutable | State never changes after creation (`frozen=True`) |
| No identity | Two instances with same values are interchangeable |
| Self-validating | `__post_init__` rejects invalid values |
| Side-effect free | Methods return new instances |

## Patterns

### Basic Value Object

A frozen dataclass gives you immutability, value equality, and hashability for
free. Normalize in a factory (`classmethod`) and validate in `__post_init__`.

```python
import re
from dataclasses import dataclass

from hermes_attractor.domain.exceptions import ValidationError

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        if not _EMAIL_RE.match(self.value):
            raise ValidationError("Invalid email format")

    @classmethod
    def create(cls, value: str) -> "Email":
        return cls(value.lower().strip())

    @property
    def domain(self) -> str:
        return self.value.split("@")[1]
```

### Enum-Style Value Object

When the value is a closed set with behavior, an `enum.Enum` is the idiomatic
Python value object. Add methods for transitions/predicates.

```python
from enum import Enum

from hermes_attractor.domain.exceptions import ValidationError


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

    @classmethod
    def from_string(cls, value: str) -> "TaskStatus":
        try:
            return cls(value)
        except ValueError as exc:
            raise ValidationError(f"Invalid status: {value}") from exc

    @property
    def is_completed(self) -> bool:
        return self is TaskStatus.COMPLETED

    def can_transition_to(self, target: "TaskStatus") -> bool:
        if self is TaskStatus.PENDING:
            return target is TaskStatus.IN_PROGRESS
        if self is TaskStatus.IN_PROGRESS:
            return target in (TaskStatus.COMPLETED, TaskStatus.PENDING)
        return False  # COMPLETED is terminal
```

### Composite Value Object

Store money as integer minor units (cents) to avoid float rounding bugs.

```python
from dataclasses import dataclass

from hermes_attractor.domain.exceptions import ValidationError


@dataclass(frozen=True)
class Money:
    amount: int  # minor units, e.g. cents
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValidationError("Amount cannot be negative")
        if not (len(self.currency) == 3 and self.currency.isupper()):
            raise ValidationError("Currency must be a 3-letter ISO code")

    @classmethod
    def zero(cls, currency: str) -> "Money":
        return cls(0, currency)

    def add(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def subtract(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        if other.amount > self.amount:
            raise ValidationError("Cannot subtract: would be negative")
        return Money(self.amount - other.amount, self.currency)

    def multiply(self, factor: int) -> "Money":
        if factor < 0:
            raise ValidationError("Factor cannot be negative")
        return Money(self.amount * factor, self.currency)

    def _assert_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValidationError(
                f"Currency mismatch: {self.currency} vs {other.currency}"
            )

    def __str__(self) -> str:
        return f"{self.currency} {self.amount / 100:.2f}"
```

## Common Value Objects

### ID Value Object

```python
from dataclasses import dataclass
from uuid import UUID, uuid4

from hermes_attractor.domain.exceptions import ValidationError


@dataclass(frozen=True)
class TaskId:
    value: UUID

    @classmethod
    def create(cls) -> "TaskId":
        return cls(uuid4())

    @classmethod
    def from_string(cls, value: str) -> "TaskId":
        if not value.strip():
            raise ValidationError("TaskId cannot be empty")
        return cls(UUID(value))
```

### Date Range Value Object

```python
from dataclasses import dataclass
from datetime import date

from hermes_attractor.domain.exceptions import ValidationError


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValidationError("End date must be on or after start date")

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def overlaps(self, other: "DateRange") -> bool:
        return self.start <= other.end and self.end >= other.start

    @property
    def duration_in_days(self) -> int:
        return (self.end - self.start).days
```

### Address Value Object

```python
from dataclasses import dataclass

from hermes_attractor.domain.exceptions import ValidationError


@dataclass(frozen=True)
class Address:
    street: str
    city: str
    postal_code: str
    country: str

    def __post_init__(self) -> None:
        for name, value in (
            ("street", self.street),
            ("city", self.city),
            ("postal_code", self.postal_code),
            ("country", self.country),
        ):
            if not value.strip():
                raise ValidationError(f"{name} is required")

    def format(self) -> str:
        return f"{self.street}, {self.city}, {self.postal_code}, {self.country}"
```

## Equality and Comparison

`frozen=True` dataclasses generate value-based `__eq__` and `__hash__`
automatically — no manual `equals()` needed:

```python
# Value comparison is free
assert Money(1000, "USD") == Money(1000, "USD")

# Works in sets and as dict keys (frozen => hashable)
prices = {Money(1000, "USD"), Money(2000, "USD")}
assert Money(1000, "USD") in prices
```

## Testing Value Objects

Pure value objects need no mocks. Use `pytest.raises` for invariant violations.

```python
import pytest

from hermes_attractor.domain.exceptions import ValidationError
from hermes_attractor.domain.value_objects import Money


class TestMoneyCreation:
    def test_creates_money_with_valid_amount_and_currency(self) -> None:
        money = Money(10000, "USD")
        assert money.amount == 10000
        assert money.currency == "USD"

    def test_rejects_negative_amounts(self) -> None:
        with pytest.raises(ValidationError, match="cannot be negative"):
            Money(-10, "USD")

    def test_rejects_invalid_currency_codes(self) -> None:
        with pytest.raises(ValidationError, match="3-letter ISO"):
            Money(10, "US")


class TestMoneyOperations:
    def test_adds_same_currency(self) -> None:
        assert Money(1000, "USD").add(Money(2000, "USD")) == Money(3000, "USD")

    def test_rejects_adding_different_currencies(self) -> None:
        with pytest.raises(ValidationError, match="Currency mismatch"):
            Money(1000, "USD").add(Money(1000, "EUR"))


class TestMoneyEquality:
    def test_equals_same_value(self) -> None:
        assert Money(1000, "USD") == Money(1000, "USD")

    def test_not_equals_different_amount(self) -> None:
        assert Money(1000, "USD") != Money(2000, "USD")
```
