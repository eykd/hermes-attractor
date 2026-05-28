# GOOS Workflow: Outside-In Test-Driven Development

## The Three Test Layers

| Layer | Purpose | Characteristics |
|-------|---------|-----------------|
| **Acceptance** | Verify features work | HTTP entry point, real DB, user-visible outcomes |
| **Integration** | Verify boundaries work | Real infrastructure, one boundary per test |
| **Unit** | Verify logic works | In-memory, isolated, pure domain logic |

## Outside-In TDD Flow

```
1. Write failing acceptance test (feature level)
         ↓
2. Identify first missing role/object
         ↓
3. Write unit test for that role
         ↓
4. Implement minimal code to pass
         ↓
5. Repeat steps 2-4 until acceptance test passes
         ↓
6. Refactor with confidence
```

## Step-by-Step Example

### 1. Start with Failing Acceptance Test
```python
def test_customer_can_place_order(client):
    response = client.post("/orders/", {"product_id": 1, "quantity": 2})

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
```
This fails—nothing exists yet.

### 2. Identify Missing Role
What's needed first? An `OrderService` to handle the business logic.

### 3. Write Unit Test for the Role
```python
class TestOrderService:
    def test_creates_order_for_available_product(self, mocker):
        # Mock the collaborator (inventory)
        inventory = mocker.Mock()
        inventory.check_stock.return_value = True

        service = OrderService(inventory=inventory)

        order = service.create(product_id=1, quantity=2)

        assert order.status == "pending"
        assert order.product_id == 1
        inventory.check_stock.assert_called_with(product_id=1, quantity=2)

    def test_rejects_order_when_out_of_stock(self, mocker):
        inventory = mocker.Mock()
        inventory.check_stock.return_value = False

        service = OrderService(inventory=inventory)

        with pytest.raises(OutOfStockError):
            service.create(product_id=1, quantity=2)
```

### 4. Implement Minimal Code
```python
class OrderService:
    def __init__(self, inventory):
        self.inventory = inventory

    def create(self, product_id, quantity):
        if not self.inventory.check_stock(product_id, quantity):
            raise OutOfStockError(product_id)
        return Order(product_id=product_id, quantity=quantity, status="pending")
```

### 5. Continue for Other Roles
- `InventoryRepository` (integration test with real DB)
- `OrderRepository` (integration test with real DB)
- View/controller to wire everything together

### 6. Acceptance Test Passes
Once all pieces are in place, the original acceptance test goes green.

## Ports and Adapters Pattern

GOOS naturally leads to clean boundaries:

```
┌─────────────────────────────────────────────────┐
│                  Domain Logic                    │
│  (OrderService, pricing rules, validations)     │
└──────────────────────┬──────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
    │  Port   │   │  Port   │   │  Port   │
    │ (Repo)  │   │ (Email) │   │(Payment)│
    └────┬────┘   └────┬────┘   └────┬────┘
         │             │             │
    ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
    │ Adapter │   │ Adapter │   │ Adapter │
    │(Postgres)│  │ (SMTP)  │   │(Stripe) │
    └─────────┘   └─────────┘   └─────────┘
```

### Port (Interface)
```python
class UserRepository(Protocol):
    def save(self, user: User) -> None: ...
    def get_by_id(self, id: int) -> User: ...
```

### Adapter (Implementation)
```python
class PostgresUserRepository:
    def __init__(self, connection):
        self.conn = connection

    def save(self, user: User) -> None:
        self.conn.execute("INSERT INTO users ...")

    def get_by_id(self, id: int) -> User:
        row = self.conn.execute("SELECT * FROM users WHERE id = ?", id)
        return User(**row)
```

### Testing Strategy
```python
# Unit test: Mock the port
def test_user_service_saves_user(mocker):
    mock_repo = mocker.Mock(spec=UserRepository)
    service = UserService(repository=mock_repo)

    service.register(email="alice@example.com")

    mock_repo.save.assert_called_once()

# Integration test: Test the adapter with real DB
def test_postgres_repository_roundtrip(test_db):
    repo = PostgresUserRepository(test_db)
    user = User(email="alice@example.com")

    repo.save(user)
    loaded = repo.get_by_id(user.id)

    assert loaded.email == "alice@example.com"
```

## Designing Through Messages

Instead of asking "What should this class contain?", ask "What messages does this object send and receive?"

### Discovering Roles via Tests
```python
def test_checkout_completes_order(mocker):
    # These mocks reveal the collaborators needed
    inventory = mocker.Mock()
    payment = mocker.Mock()
    notifier = mocker.Mock()

    checkout = CheckoutService(
        inventory=inventory,
        payment=payment,
        notifier=notifier
    )

    checkout.complete(order_id=1)

    # Tests reveal the messages/protocol
    inventory.reserve.assert_called()
    payment.charge.assert_called()
    notifier.send_confirmation.assert_called()
```

Each mock assertion reveals a **role** your system needs:
- Something that reserves inventory
- Something that charges payment
- Something that sends notifications

## Unit Test Template (GOOS Style)

```python
class TestOrderService:
    """Unit tests for OrderService business logic."""

    def test_creates_pending_order_for_valid_request(self, mocker):
        # Arrange: Set up collaborators
        repo = mocker.Mock(spec=OrderRepository)
        inventory = mocker.Mock(spec=InventoryService)
        inventory.is_available.return_value = True

        service = OrderService(repository=repo, inventory=inventory)

        # Act: Execute behavior
        order = service.create(product_id=1, customer_id=1)

        # Assert: Verify outcomes and collaborations
        assert order.status == "pending"
        repo.save.assert_called_once_with(order)
        inventory.is_available.assert_called_with(product_id=1)
```

## Integration Test Template (GOOS Style)

```python
class TestOrderRepository:
    """Integration tests for OrderRepository persistence."""

    def test_saves_and_retrieves_order(self, test_database):
        # Arrange: Real repository, real DB
        repo = PostgresOrderRepository(test_database)
        order = Order(product_id=1, status="pending")

        # Act: Real persistence
        repo.save(order)
        loaded = repo.get_by_id(order.id)

        # Assert: Real side effects
        assert loaded.product_id == 1
        assert loaded.status == "pending"
```

## Acceptance Test Template (GOOS Style)

```python
class TestPlaceOrder:
    """Acceptance test for order placement feature."""

    def test_customer_can_place_order_for_available_product(self, client, available_product):
        # Given: A product in stock
        # (available_product fixture creates real DB record)

        # When: Customer places order via HTTP
        response = client.post("/orders/", {
            "product_id": available_product.id,
            "quantity": 1
        })

        # Then: Order is created
        assert response.status_code == 201
        assert response.json()["status"] == "pending"

        # And: Order exists in database
        order_id = response.json()["id"]
        assert Order.objects.filter(id=order_id).exists()
```

## When Tests Are Hard to Write

| Symptom | Diagnosis | Solution |
|---------|-----------|----------|
| Too many mocks | Object has too many collaborators | Split into smaller objects |
| Complex setup | Object knows too much | Reduce dependencies |
| Mocking internals | Testing implementation | Test via public interface |
| Brittle to refactoring | Over-specified interactions | Assert on outcomes, not steps |
