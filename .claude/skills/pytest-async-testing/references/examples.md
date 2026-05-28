# Real-World Async Testing Examples

Complete examples for common async testing scenarios.

## Example 1: Async HTTP Client

### Production Code

```python
# client.py
import aiohttp

class WeatherClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.weather.com"

    async def get_forecast(self, city: str) -> dict:
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/forecast"
            params = {"city": city, "key": self.api_key}
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    raise ValueError(f"City not found: {city}")
                else:
                    raise RuntimeError(f"API error: {resp.status}")
```

### Tests

```python
# test_client.py
import pytest
from unittest.mock import AsyncMock
from client import WeatherClient

@pytest.fixture
def weather_client():
    return WeatherClient(api_key="test-key")

@pytest.mark.asyncio
async def test_get_forecast_success(mocker, weather_client):
    # Arrange
    expected = {"temp": 72, "conditions": "sunny"}
    mocker.patch.object(
        WeatherClient,
        "get_forecast",
        AsyncMock(return_value=expected)
    )

    # Act
    result = await weather_client.get_forecast("Seattle")

    # Assert
    assert result["temp"] == 72
    assert result["conditions"] == "sunny"

@pytest.mark.asyncio
async def test_get_forecast_city_not_found(mocker, weather_client):
    mocker.patch.object(
        WeatherClient,
        "get_forecast",
        AsyncMock(side_effect=ValueError("City not found: InvalidCity"))
    )

    with pytest.raises(ValueError, match="City not found"):
        await weather_client.get_forecast("InvalidCity")

@pytest.mark.asyncio
async def test_get_forecast_api_error(mocker, weather_client):
    mocker.patch.object(
        WeatherClient,
        "get_forecast",
        AsyncMock(side_effect=RuntimeError("API error: 500"))
    )

    with pytest.raises(RuntimeError, match="API error"):
        await weather_client.get_forecast("Seattle")
```

## Example 2: Async Repository Pattern

### Production Code

```python
# repository.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    id: int
    name: str
    email: str

class UserRepository:
    def __init__(self, db_pool):
        self.pool = db_pool

    async def get_by_id(self, user_id: int) -> Optional[User]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, name, email FROM users WHERE id = $1",
                user_id
            )
            if row:
                return User(**dict(row))
            return None

    async def create(self, name: str, email: str) -> User:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO users (name, email) VALUES ($1, $2) RETURNING id, name, email",
                name, email
            )
            return User(**dict(row))

    async def delete(self, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM users WHERE id = $1",
                user_id
            )
            return result == "DELETE 1"
```

### Tests

```python
# test_repository.py
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from repository import UserRepository, User

@pytest_asyncio.fixture
async def mock_pool():
    pool = AsyncMock()
    return pool

@pytest_asyncio.fixture
async def user_repo(mock_pool):
    return UserRepository(db_pool=mock_pool)

def make_mock_connection(fetchrow_result=None, execute_result=None):
    """Helper to create mock database connection."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    conn.execute = AsyncMock(return_value=execute_result)
    return conn

@pytest.mark.asyncio
async def test_get_by_id_found(mock_pool, user_repo):
    # Arrange
    mock_conn = make_mock_connection(
        fetchrow_result={"id": 1, "name": "Alice", "email": "alice@example.com"}
    )
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Act
    user = await user_repo.get_by_id(1)

    # Assert
    assert user is not None
    assert user.id == 1
    assert user.name == "Alice"
    mock_conn.fetchrow.assert_called_once()

@pytest.mark.asyncio
async def test_get_by_id_not_found(mock_pool, user_repo):
    mock_conn = make_mock_connection(fetchrow_result=None)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    user = await user_repo.get_by_id(999)

    assert user is None

@pytest.mark.asyncio
async def test_create_user(mock_pool, user_repo):
    mock_conn = make_mock_connection(
        fetchrow_result={"id": 1, "name": "Bob", "email": "bob@example.com"}
    )
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    user = await user_repo.create("Bob", "bob@example.com")

    assert user.id == 1
    assert user.name == "Bob"

@pytest.mark.asyncio
async def test_delete_user_success(mock_pool, user_repo):
    mock_conn = make_mock_connection(execute_result="DELETE 1")
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    result = await user_repo.delete(1)

    assert result is True

@pytest.mark.asyncio
async def test_delete_user_not_found(mock_pool, user_repo):
    mock_conn = make_mock_connection(execute_result="DELETE 0")
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    result = await user_repo.delete(999)

    assert result is False
```

## Example 3: Async Service with Multiple Dependencies

### Production Code

```python
# service.py
class OrderService:
    def __init__(self, user_repo, product_repo, payment_client, email_client):
        self.user_repo = user_repo
        self.product_repo = product_repo
        self.payment = payment_client
        self.email = email_client

    async def place_order(self, user_id: int, product_id: int, quantity: int) -> dict:
        # Fetch user and product concurrently
        user, product = await asyncio.gather(
            self.user_repo.get_by_id(user_id),
            self.product_repo.get_by_id(product_id)
        )

        if not user:
            raise ValueError("User not found")
        if not product:
            raise ValueError("Product not found")
        if product.stock < quantity:
            raise ValueError("Insufficient stock")

        total = product.price * quantity

        # Process payment
        payment_result = await self.payment.charge(user.id, total)
        if not payment_result.success:
            raise RuntimeError("Payment failed")

        # Send confirmation email (fire and forget)
        asyncio.create_task(
            self.email.send_order_confirmation(user.email, product.name, quantity)
        )

        return {
            "order_id": payment_result.transaction_id,
            "total": total,
            "status": "confirmed"
        }
```

### Tests

```python
# test_service.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass

@dataclass
class MockUser:
    id: int
    email: str

@dataclass
class MockProduct:
    id: int
    name: str
    price: float
    stock: int

@dataclass
class MockPaymentResult:
    success: bool
    transaction_id: str

@pytest.fixture
def mock_user_repo():
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=MockUser(id=1, email="test@example.com"))
    return repo

@pytest.fixture
def mock_product_repo():
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=MockProduct(
        id=1, name="Widget", price=10.0, stock=100
    ))
    return repo

@pytest.fixture
def mock_payment():
    client = AsyncMock()
    client.charge = AsyncMock(return_value=MockPaymentResult(
        success=True, transaction_id="txn_123"
    ))
    return client

@pytest.fixture
def mock_email():
    client = AsyncMock()
    client.send_order_confirmation = AsyncMock()
    return client

@pytest.fixture
def order_service(mock_user_repo, mock_product_repo, mock_payment, mock_email):
    return OrderService(
        user_repo=mock_user_repo,
        product_repo=mock_product_repo,
        payment_client=mock_payment,
        email_client=mock_email
    )

@pytest.mark.asyncio
async def test_place_order_success(order_service, mock_payment):
    result = await order_service.place_order(
        user_id=1, product_id=1, quantity=2
    )

    assert result["order_id"] == "txn_123"
    assert result["total"] == 20.0
    assert result["status"] == "confirmed"
    mock_payment.charge.assert_called_once_with(1, 20.0)

@pytest.mark.asyncio
async def test_place_order_user_not_found(order_service, mock_user_repo):
    mock_user_repo.get_by_id.return_value = None

    with pytest.raises(ValueError, match="User not found"):
        await order_service.place_order(user_id=999, product_id=1, quantity=1)

@pytest.mark.asyncio
async def test_place_order_insufficient_stock(order_service, mock_product_repo):
    mock_product_repo.get_by_id.return_value = MockProduct(
        id=1, name="Widget", price=10.0, stock=5
    )

    with pytest.raises(ValueError, match="Insufficient stock"):
        await order_service.place_order(user_id=1, product_id=1, quantity=10)

@pytest.mark.asyncio
async def test_place_order_payment_failed(order_service, mock_payment):
    mock_payment.charge.return_value = MockPaymentResult(
        success=False, transaction_id=""
    )

    with pytest.raises(RuntimeError, match="Payment failed"):
        await order_service.place_order(user_id=1, product_id=1, quantity=1)
```

## Example 4: WebSocket Testing

### Production Code

```python
# websocket_handler.py
class ChatHandler:
    def __init__(self):
        self.connections = set()

    async def handle_connection(self, websocket):
        self.connections.add(websocket)
        try:
            async for message in websocket:
                await self.broadcast(message)
        finally:
            self.connections.discard(websocket)

    async def broadcast(self, message: str):
        for conn in self.connections:
            await conn.send(message)
```

### Tests

```python
# test_websocket.py
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def chat_handler():
    return ChatHandler()

@pytest.fixture
def mock_websocket():
    ws = AsyncMock()
    ws.send = AsyncMock()
    return ws

@pytest.mark.asyncio
async def test_broadcast_to_all_connections(chat_handler, mock_websocket):
    # Create multiple mock connections
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws3 = AsyncMock()

    chat_handler.connections = {ws1, ws2, ws3}

    await chat_handler.broadcast("Hello everyone!")

    ws1.send.assert_called_once_with("Hello everyone!")
    ws2.send.assert_called_once_with("Hello everyone!")
    ws3.send.assert_called_once_with("Hello everyone!")

@pytest.mark.asyncio
async def test_connection_added_and_removed(chat_handler, mock_websocket):
    # Simulate receiving messages then disconnecting
    mock_websocket.__aiter__.return_value = iter(["msg1", "msg2"])

    await chat_handler.handle_connection(mock_websocket)

    assert mock_websocket not in chat_handler.connections
```

## Example 5: Async Context Manager Testing

### Production Code

```python
# connection_pool.py
class AsyncConnectionPool:
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.available = asyncio.Queue()
        self.in_use = 0
        self._initialized = False

    async def __aenter__(self):
        if not self._initialized:
            for _ in range(self.max_connections):
                await self.available.put(await self._create_connection())
            self._initialized = True
        return self

    async def __aexit__(self, *args):
        while not self.available.empty():
            conn = await self.available.get()
            await conn.close()

    async def _create_connection(self):
        # Simulate creating connection
        return AsyncMock()

    async def acquire(self):
        conn = await self.available.get()
        self.in_use += 1
        return conn

    async def release(self, conn):
        self.in_use -= 1
        await self.available.put(conn)
```

### Tests

```python
# test_connection_pool.py
import pytest
import asyncio
from connection_pool import AsyncConnectionPool

@pytest.mark.asyncio
async def test_pool_initializes_connections():
    async with AsyncConnectionPool(max_connections=5) as pool:
        assert pool.available.qsize() == 5

@pytest.mark.asyncio
async def test_acquire_and_release():
    async with AsyncConnectionPool(max_connections=3) as pool:
        conn = await pool.acquire()
        assert pool.in_use == 1
        assert pool.available.qsize() == 2

        await pool.release(conn)
        assert pool.in_use == 0
        assert pool.available.qsize() == 3

@pytest.mark.asyncio
async def test_concurrent_acquire():
    async with AsyncConnectionPool(max_connections=3) as pool:
        # Acquire all connections concurrently
        conns = await asyncio.gather(
            pool.acquire(),
            pool.acquire(),
            pool.acquire()
        )

        assert len(conns) == 3
        assert pool.in_use == 3
        assert pool.available.qsize() == 0
```

## Example 6: Testing Async Retry Logic

### Production Code

```python
# retry.py
import asyncio

async def with_retry(coro_func, max_attempts=3, delay=1.0):
    """Execute async function with retry logic."""
    last_exception = None

    for attempt in range(max_attempts):
        try:
            return await coro_func()
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)

    raise last_exception
```

### Tests

```python
# test_retry.py
import pytest
from unittest.mock import AsyncMock
from retry import with_retry

@pytest.mark.asyncio
async def test_retry_succeeds_first_attempt():
    mock_func = AsyncMock(return_value="success")

    result = await with_retry(mock_func, max_attempts=3)

    assert result == "success"
    assert mock_func.call_count == 1

@pytest.mark.asyncio
async def test_retry_succeeds_after_failures():
    mock_func = AsyncMock(side_effect=[
        ValueError("fail 1"),
        ValueError("fail 2"),
        "success"
    ])

    result = await with_retry(mock_func, max_attempts=3, delay=0)

    assert result == "success"
    assert mock_func.call_count == 3

@pytest.mark.asyncio
async def test_retry_exhausted():
    mock_func = AsyncMock(side_effect=ValueError("always fails"))

    with pytest.raises(ValueError, match="always fails"):
        await with_retry(mock_func, max_attempts=3, delay=0)

    assert mock_func.call_count == 3
```
