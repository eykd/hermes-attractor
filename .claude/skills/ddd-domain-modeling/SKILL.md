---
name: ddd-domain-modeling
description: Create pure Python domain models following Domain-Driven Design principles. Use when building domain entities with validation and invariants, value objects with encapsulation, repository interfaces, or domain services. Also use for questions about keeping domain code free of external dependencies, enforcing business rules in the domain layer, or implementing tactical DDD patterns. Triggers on mentions of DDD, domain model, entity, value object, aggregate, repository interface, domain service, or business logic encapsulation.
---

# DDD Domain Modeling

Create domain models in pure Python with zero external dependencies. The domain
lives in `src/hermes_attractor/domain/` and may import only the standard library.

## Core Principle

The domain layer contains **pure business logic only**:
- No framework imports (no Hermes APIs, no HTTP/DB clients)
- No async operations in entities/value objects
- No database or I/O concerns
- Validate invariants in `__post_init__` / constructors
- Dependencies point inward (plugin → use_cases/adapters → ports → domain)

## Directory Structure

```
src/hermes_attractor/domain/
├── entities.py         # Aggregate roots and entities (mutable, have identity)
├── value_objects.py    # Immutable value types (frozen dataclasses)
├── services.py         # Stateless domain logic
└── exceptions.py       # Domain exception hierarchy
```

Repository *interfaces* (ports) live one layer out, in
`src/hermes_attractor/ports/`, as `typing.Protocol` definitions.

## Quick Reference

### Entity (identity + lifecycle + behavior)
```python
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from hermes_attractor.domain.exceptions import ValidationError


@dataclass
class Order:
    id: UUID
    customer_id: UUID
    _items: list["LineItem"] = field(default_factory=list)

    @classmethod
    def create(cls, customer_id: UUID) -> "Order":
        """Factory enforcing invariants for a brand-new Order."""
        return cls(id=uuid4(), customer_id=customer_id)

    def add_item(self, item: "LineItem") -> None:
        """Behavior method that protects invariants — no public setters."""
        if any(i.product_id == item.product_id for i in self._items):
            raise ValidationError("Item already present")
        self._items.append(item)

    @property
    def items(self) -> tuple["LineItem", ...]:
        return tuple(self._items)  # expose a read-only view
```

Identity is by `id`, not by attribute equality — leave entities as a mutable
(non-frozen) `@dataclass` and compare on `id`.

### Value Object (immutable, equality by value)
```python
from dataclasses import dataclass

from hermes_attractor.domain.exceptions import ValidationError


@dataclass(frozen=True)
class Money:
    amount: int  # store minor units (cents) to avoid float rounding
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValidationError("Amount cannot be negative")
        if len(self.currency) != 3:
            raise ValidationError("Currency must be a 3-letter ISO code")

    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValidationError("Currency mismatch")
        return Money(self.amount + other.amount, self.currency)
```

`frozen=True` makes the dataclass immutable and hashable, and gives you
value-based `__eq__` for free.

### Repository Interface (a port — `Protocol`)
```python
# src/hermes_attractor/ports/order_repository.py
from typing import Protocol
from uuid import UUID

from hermes_attractor.domain.entities import Order


class OrderRepository(Protocol):
    def find_by_id(self, order_id: UUID) -> Order | None: ...
    def save(self, order: Order) -> None: ...
```

The domain defines *what* it needs; adapters in
`src/hermes_attractor/adapters/` implement *how*.

### Domain Service (stateless, multi-object logic)
```python
# src/hermes_attractor/domain/services.py
from collections.abc import Sequence


class PricingService:
    """Stateless logic that doesn't belong to a single entity/value object."""

    def calculate_total(
        self, items: Sequence["LineItem"], discounts: Sequence["Discount"]
    ) -> Money:
        ...  # complex calculation across multiple objects
```

## Workflow

1. **Identify the concept**: Entity (has identity) or Value Object (defined by its attributes)?
2. **Define invariants**: What rules must always be true? Enforce them in `__post_init__`/factories.
3. **Choose pattern**: See detailed references below.
4. **Write tests first**: Domain code is pure — test without mocks.

## Detailed References

- **Entities with identity and lifecycle**: See [references/entities.md](references/entities.md)
- **Value Objects with validation**: See [references/value-objects.md](references/value-objects.md)
- **Repository interfaces (ports)**: See [references/repositories.md](references/repositories.md)
- **Domain services for complex logic**: See [references/domain-services.md](references/domain-services.md)

## Anti-Patterns to Avoid

| Anti-Pattern | Instead |
|--------------|---------|
| `import httpx`/Hermes APIs in domain | Define a `Protocol` port in domain/ports, implement in adapters |
| `async def` in entity methods | Keep entities synchronous; async belongs in adapters/use_cases |
| Exposing mutable attributes | Provide behavior methods: `order.add_item()` not `order.items.append(...)` |
| Validation in the use_case layer | Validate in entity/value-object `__post_init__`/factories |
| Anemic domain model (data bags) | Put behavior with the data it operates on |
| Comparing entities by all fields | Compare by `id`; only value objects use value equality |
