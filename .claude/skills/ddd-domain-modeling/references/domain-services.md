# Domain Services

Domain services contain business logic that doesn't naturally fit within a single
entity or value object. They live in `src/hermes_attractor/domain/services.py`.

## Table of Contents
- [When to Use Domain Services](#when-to-use-domain-services)
- [Characteristics](#characteristics)
- [Patterns](#patterns)
- [Testing Domain Services](#testing-domain-services)

## When to Use Domain Services

Use a domain service when the operation:
- Involves multiple entities or aggregates
- Requires business logic that doesn't belong to any single entity
- Implements a domain concept that is a "verb" rather than a "noun"
- Needs to enforce cross-entity invariants

| Scenario | Solution |
|----------|----------|
| Calculate order total from line items | Entity method: `order.calculate_total()` |
| Check if user can afford a purchase | Domain service: `PaymentEligibilityService` |
| Transfer funds between accounts | Domain service: `FundsTransferService` |
| Validate an email format | Value object: `Email.create()` |

## Characteristics

Domain services are:
- **Stateless**: No instance state, operate purely on inputs
- **Pure**: No side effects, same inputs produce same outputs
- **Framework-free**: No database, HTTP, or Hermes dependencies
- **Synchronous**: No `async`/I/O (those belong in adapters/use_cases)

```python
from collections.abc import Sequence


# ✅ Good: pure domain service
class PricingService:
    def calculate_discount(
        self, items: Sequence["LineItem"], customer_tier: "CustomerTier"
    ) -> "Money":
        ...  # pure calculation logic


# ❌ Bad: has infrastructure concerns
class PricingService:
    def __init__(self, db: "Database") -> None:  # infrastructure dependency
        self._db = db

    async def calculate_discount(self, customer_id: UUID) -> "Money":  # async I/O
        customer = await self._db.find_customer(customer_id)
        ...
```

## Patterns

### Calculation Service

Money is stored in integer minor units (cents); discount percentages are applied
with integer-safe arithmetic to avoid float rounding.

```python
# src/hermes_attractor/domain/services.py
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from hermes_attractor.domain.value_objects import Money


class DiscountType(Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


@dataclass(frozen=True)
class Discount:
    type: DiscountType
    value: int  # percent points, or minor units for FIXED


class PricingService:
    def calculate_subtotal(self, items: Sequence["LineItem"]) -> Money:
        if not items:
            return Money.zero("USD")
        total = Money.zero(items[0].price.currency)
        for item in items:
            total = total.add(item.price.multiply(item.quantity))
        return total

    def apply_discounts(
        self, subtotal: Money, discounts: Sequence[Discount]
    ) -> Money:
        total = subtotal
        # Percentage discounts first, then fixed
        ordered = sorted(
            discounts, key=lambda d: d.type is not DiscountType.PERCENTAGE
        )
        for discount in ordered:
            if discount.type is DiscountType.PERCENTAGE:
                reduction = Money(
                    total.amount * discount.value // 100, total.currency
                )
            else:
                reduction = Money(discount.value, total.currency)
            if reduction.amount >= total.amount:
                return Money.zero(total.currency)  # never go below zero
            total = total.subtract(reduction)
        return total

    def calculate_tax(self, amount: Money, tax_rate_pct: int) -> Money:
        return Money(amount.amount * tax_rate_pct // 100, amount.currency)
```

### Validation Service

```python
# src/hermes_attractor/domain/services.py
from dataclasses import dataclass, field

from hermes_attractor.domain.entities import Customer, Order
from hermes_attractor.domain.value_objects import Money


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.errors


class OrderValidationService:
    def validate_order(self, order: Order, customer: Customer) -> ValidationResult:
        errors: list[str] = []

        # Business rule: customer must be active
        if not customer.is_active:
            errors.append("Customer account is not active")

        # Business rule: order value within customer's credit limit
        if order.total.amount > customer.credit_limit.amount:
            errors.append("Order exceeds customer credit limit")

        # Business rule: minimum order value ($10 = 1000 cents)
        if order.total.amount < 1000:
            errors.append("Order must be at least $10")

        # Business rule: no more than 100 items per order
        if order.item_count > 100:
            errors.append("Order cannot exceed 100 items")

        return ValidationResult(errors=tuple(errors))
```

### Policy Service

```python
# src/hermes_attractor/domain/services.py
from dataclasses import dataclass

from hermes_attractor.domain.entities import Order
from hermes_attractor.domain.value_objects import Address, Money

_FREE_SHIPPING_THRESHOLD = 5000  # $50 in cents


@dataclass(frozen=True)
class ShippingOption:
    name: str
    cost: Money
    estimated_days: int


class ShippingPolicyService:
    def get_available_options(
        self, order: Order, destination: Address
    ) -> list[ShippingOption]:
        currency = order.total.currency
        options = [
            ShippingOption(
                name="Standard",
                cost=self._standard_cost(order, destination),
                estimated_days=5 if destination.country == "US" else 14,
            )
        ]

        # Express available for orders under 50 lbs
        if order.total_weight < 50:
            options.append(
                ShippingOption("Express", Money(1599, currency), estimated_days=2)
            )

        # Overnight for domestic only
        if destination.country == "US":
            options.append(
                ShippingOption("Overnight", Money(2999, currency), estimated_days=1)
            )

        return options

    def _standard_cost(self, order: Order, destination: Address) -> Money:
        currency = order.total.currency
        if order.total.amount >= _FREE_SHIPPING_THRESHOLD:
            return Money.zero(currency)
        base = 599 if destination.country == "US" else 1499
        surcharge = max(0, (order.total_weight - 5)) * 50  # cents per lb
        return Money(base + surcharge, currency)
```

### Allocation/Distribution Service

```python
# src/hermes_attractor/domain/services.py
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from hermes_attractor.domain.entities import OrderItem, WarehouseStock


@dataclass(frozen=True)
class WarehouseAllocation:
    warehouse_id: UUID
    quantity: int


@dataclass(frozen=True)
class Unallocated:
    product_id: UUID
    quantity: int


@dataclass(frozen=True)
class AllocationResult:
    allocations: dict[UUID, list[WarehouseAllocation]]
    unallocated: list[Unallocated]


class InventoryAllocationService:
    def allocate_stock(
        self,
        items: Sequence[OrderItem],
        warehouse_stocks: Sequence[WarehouseStock],
    ) -> AllocationResult:
        allocations: dict[UUID, list[WarehouseAllocation]] = {}
        unallocated: list[Unallocated] = []

        for item in items:
            product_allocations: list[WarehouseAllocation] = []
            remaining = item.quantity

            # Highest-available warehouse first
            sorted_stocks = sorted(
                (s for s in warehouse_stocks if s.product_id == item.product_id),
                key=lambda s: s.available,
                reverse=True,
            )

            for stock in sorted_stocks:
                if remaining <= 0:
                    break
                allocate = min(remaining, stock.available)
                if allocate > 0:
                    product_allocations.append(
                        WarehouseAllocation(stock.warehouse_id, allocate)
                    )
                    remaining -= allocate

            if product_allocations:
                allocations[item.product_id] = product_allocations
            if remaining > 0:
                unallocated.append(Unallocated(item.product_id, remaining))

        return AllocationResult(allocations=allocations, unallocated=unallocated)
```

## Testing Domain Services

Domain services are pure — test without mocks.

```python
from uuid import uuid4

import pytest

from hermes_attractor.domain.services import (
    Discount,
    DiscountType,
    PricingService,
)
from hermes_attractor.domain.value_objects import Money


def make_line_item(price: Money, quantity: int) -> "LineItem":
    return LineItem.create(product_id=uuid4(), price=price, quantity=quantity)


class TestCalculateSubtotal:
    def test_sums_all_line_items(self) -> None:
        service = PricingService()
        items = [
            make_line_item(Money(1000, "USD"), 2),
            make_line_item(Money(500, "USD"), 3),
        ]
        # (1000*2) + (500*3) = 3500
        assert service.calculate_subtotal(items) == Money(3500, "USD")

    def test_returns_zero_for_empty_items(self) -> None:
        assert PricingService().calculate_subtotal([]) == Money.zero("USD")


class TestApplyDiscounts:
    def test_applies_percentage_discount(self) -> None:
        result = PricingService().apply_discounts(
            Money(10000, "USD"), [Discount(DiscountType.PERCENTAGE, 10)]
        )
        assert result == Money(9000, "USD")

    def test_applies_fixed_discount(self) -> None:
        result = PricingService().apply_discounts(
            Money(10000, "USD"), [Discount(DiscountType.FIXED, 1500)]
        )
        assert result == Money(8500, "USD")

    def test_applies_percentage_before_fixed(self) -> None:
        result = PricingService().apply_discounts(
            Money(10000, "USD"),
            [Discount(DiscountType.FIXED, 1000), Discount(DiscountType.PERCENTAGE, 10)],
        )
        # 10000 - 10% = 9000, then 9000 - 1000 = 8000
        assert result == Money(8000, "USD")

    def test_never_returns_negative(self) -> None:
        result = PricingService().apply_discounts(
            Money(1000, "USD"), [Discount(DiscountType.FIXED, 5000)]
        )
        assert result == Money.zero("USD")
```

### Integration with Use Cases

Use cases (in `src/hermes_attractor/use_cases/`) orchestrate domain services and
ports. They receive collaborators via constructor injection.

```python
# src/hermes_attractor/use_cases/place_order.py
from dataclasses import dataclass
from uuid import UUID

from hermes_attractor.domain.entities import Order
from hermes_attractor.domain.exceptions import NotFoundError
from hermes_attractor.domain.services import (
    OrderValidationService,
    PricingService,
    ShippingPolicyService,
)
from hermes_attractor.ports.customer_repository import CustomerRepository
from hermes_attractor.ports.order_repository import OrderRepository


@dataclass(frozen=True)
class PlaceOrderResult:
    order_id: UUID | None
    errors: tuple[str, ...] = ()

    @property
    def success(self) -> bool:
        return self.order_id is not None


class PlaceOrder:
    def __init__(
        self,
        order_repository: OrderRepository,
        customer_repository: CustomerRepository,
        pricing_service: PricingService,
        shipping_service: ShippingPolicyService,
        validation_service: OrderValidationService,
    ) -> None:
        self._orders = order_repository
        self._customers = customer_repository
        self._pricing = pricing_service
        self._shipping = shipping_service
        self._validation = validation_service

    def execute(self, request: "PlaceOrderRequest") -> PlaceOrderResult:
        customer = self._customers.find_by_id(request.customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")

        # Use domain services for business logic
        subtotal = self._pricing.calculate_subtotal(request.items)
        after_discounts = self._pricing.apply_discounts(subtotal, request.discounts)

        order = Order.create(customer_id=customer.id)
        for item in request.items:
            order.add_item(item)

        # Validate using a domain service
        result = self._validation.validate_order(order, customer)
        if not result.is_valid:
            return PlaceOrderResult(order_id=None, errors=result.errors)

        self._orders.save(order)
        return PlaceOrderResult(order_id=order.id)
```
