# Django Async Testing

Django-specific patterns for testing async views, ORM operations, and Channels.

## Setup

```bash
uv add --group=test pytest pytest-asyncio pytest-django pytest-mock
```

### pytest.ini

```ini
[pytest]
DJANGO_SETTINGS_MODULE = myproject.settings
asyncio_mode = auto
python_files = test_*.py
```

### conftest.py

```python
import pytest

@pytest.fixture(scope="session")
def django_db_setup():
    """Configure test database."""
    pass

@pytest.fixture
def async_client():
    """Async test client for Django 4.1+."""
    from django.test import AsyncClient
    return AsyncClient()
```

## Async Views

### Production Code

```python
# views.py
from django.http import JsonResponse

async def async_user_detail(request, user_id):
    user = await User.objects.aget(id=user_id)
    return JsonResponse({
        "id": user.id,
        "name": user.name,
        "email": user.email
    })

async def async_user_list(request):
    users = [user async for user in User.objects.all()]
    return JsonResponse({
        "users": [{"id": u.id, "name": u.name} for u in users]
    })
```

### Testing Async Views

```python
# test_views.py
import pytest
from django.test import AsyncClient

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_async_user_detail(async_client):
    # Create test user
    user = await User.objects.acreate(name="Alice", email="alice@example.com")

    response = await async_client.get(f"/api/users/{user.id}/")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Alice"

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_async_user_list(async_client):
    await User.objects.acreate(name="Alice", email="alice@example.com")
    await User.objects.acreate(name="Bob", email="bob@example.com")

    response = await async_client.get("/api/users/")

    assert response.status_code == 200
    data = response.json()
    assert len(data["users"]) == 2
```

## Async ORM (Django 4.1+)

Django 4.1+ provides async ORM methods prefixed with `a`:

| Sync Method | Async Method |
|-------------|--------------|
| `.get()` | `.aget()` |
| `.create()` | `.acreate()` |
| `.update()` | `.aupdate()` |
| `.delete()` | `.adelete()` |
| `.count()` | `.acount()` |
| `.exists()` | `.aexists()` |
| `.first()` | `.afirst()` |
| `.last()` | `.alast()` |
| `.save()` | `.asave()` |
| `.refresh_from_db()` | `.arefresh_from_db()` |

### Async Iteration

```python
# Async iteration over queryset
async for user in User.objects.filter(active=True):
    print(user.name)

# Async list comprehension
users = [u async for u in User.objects.all()]
```

### Testing Async ORM

```python
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_async_orm_operations():
    # Create
    user = await User.objects.acreate(name="Test", email="test@example.com")
    assert user.id is not None

    # Read
    fetched = await User.objects.aget(id=user.id)
    assert fetched.name == "Test"

    # Update
    user.name = "Updated"
    await user.asave()

    # Verify
    await user.arefresh_from_db()
    assert user.name == "Updated"

    # Delete
    await user.adelete()
    assert not await User.objects.filter(id=user.id).aexists()
```

## Database Markers

### Transaction Modes

```python
# Standard - uses transaction rollback (faster)
@pytest.mark.django_db
async def test_with_rollback():
    ...

# Transaction=True - commits transactions (required for async)
@pytest.mark.django_db(transaction=True)
async def test_with_commit():
    ...

# Reset sequences (for predictable IDs)
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_with_reset():
    ...
```

**Important**: Async tests typically require `transaction=True` because Django's async ORM uses database connections that can't participate in the test's transaction.

## Mocking in Django Async Tests

### Mock Async View Dependencies

```python
# views.py
async def fetch_external_data(request):
    data = await external_api.fetch()
    return JsonResponse(data)

# test_views.py
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_external_data_view(mocker, async_client):
    mocker.patch(
        "myapp.views.external_api.fetch",
        AsyncMock(return_value={"key": "mocked"})
    )

    response = await async_client.get("/api/external/")

    assert response.status_code == 200
    assert response.json()["key"] == "mocked"
```

### Mock Async ORM Queries

```python
@pytest.mark.asyncio
async def test_service_with_mocked_orm(mocker):
    mock_user = User(id=1, name="MockUser", email="mock@example.com")

    mocker.patch.object(
        User.objects,
        "aget",
        AsyncMock(return_value=mock_user)
    )

    service = UserService()
    result = await service.get_user(1)

    assert result.name == "MockUser"
```

## Django Channels (WebSockets)

### Setup

```bash
uv add --group=test channels pytest-asyncio
```

### Consumer Code

```python
# consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room"]
        self.room_group = f"chat_{self.room_name}"

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive_json(self, content):
        await self.channel_layer.group_send(
            self.room_group,
            {"type": "chat.message", "message": content["message"]}
        )

    async def chat_message(self, event):
        await self.send_json({"message": event["message"]})
```

### Testing Channels

```python
# test_consumers.py
import pytest
from channels.testing import WebsocketCommunicator
from myapp.consumers import ChatConsumer

@pytest.mark.asyncio
async def test_chat_connect():
    communicator = WebsocketCommunicator(
        ChatConsumer.as_asgi(),
        "/ws/chat/testroom/"
    )

    connected, _ = await communicator.connect()
    assert connected

    await communicator.disconnect()

@pytest.mark.asyncio
async def test_chat_send_receive():
    communicator = WebsocketCommunicator(
        ChatConsumer.as_asgi(),
        "/ws/chat/testroom/"
    )
    await communicator.connect()

    # Send message
    await communicator.send_json_to({"message": "Hello!"})

    # Receive broadcast
    response = await communicator.receive_json_from()
    assert response["message"] == "Hello!"

    await communicator.disconnect()

@pytest.mark.asyncio
async def test_chat_multiple_clients():
    # Two clients in same room
    comm1 = WebsocketCommunicator(ChatConsumer.as_asgi(), "/ws/chat/room1/")
    comm2 = WebsocketCommunicator(ChatConsumer.as_asgi(), "/ws/chat/room1/")

    await comm1.connect()
    await comm2.connect()

    # Client 1 sends
    await comm1.send_json_to({"message": "Hi from client 1"})

    # Both clients receive
    resp1 = await comm1.receive_json_from()
    resp2 = await comm2.receive_json_from()

    assert resp1["message"] == "Hi from client 1"
    assert resp2["message"] == "Hi from client 1"

    await comm1.disconnect()
    await comm2.disconnect()
```

### Testing with Channel Layers

```python
# conftest.py
@pytest.fixture
def channel_layers_setting(settings):
    """Use in-memory channel layer for tests."""
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
```

## Async Middleware Testing

### Middleware Code

```python
# middleware.py
class AsyncTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    async def __call__(self, request):
        import time
        start = time.perf_counter()

        response = await self.get_response(request)

        duration = time.perf_counter() - start
        response["X-Request-Duration"] = str(duration)
        return response
```

### Testing Middleware

```python
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_timing_middleware(async_client):
    response = await async_client.get("/api/users/")

    assert "X-Request-Duration" in response.headers
    duration = float(response.headers["X-Request-Duration"])
    assert duration >= 0
```

## Django REST Framework Async

### Async ViewSet

```python
# views.py
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from adrf.viewsets import ViewSet as AsyncViewSet  # django-adrf

class AsyncUserViewSet(AsyncViewSet):
    async def list(self, request):
        users = [u async for u in User.objects.all()]
        return Response([{"id": u.id, "name": u.name} for u in users])

    async def retrieve(self, request, pk=None):
        user = await User.objects.aget(pk=pk)
        return Response({"id": user.id, "name": user.name})
```

### Testing DRF Async Views

```python
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_async_viewset_list():
    from rest_framework.test import APIClient
    from asgiref.sync import sync_to_async

    # Create test data
    await User.objects.acreate(name="Alice", email="alice@example.com")

    # DRF's APIClient is sync, wrap in sync_to_async or use AsyncClient
    client = APIClient()
    response = await sync_to_async(client.get)("/api/users/")

    assert response.status_code == 200
    assert len(response.data) == 1
```

## Factory Boy with Async

```python
# factories.py
import factory
from factory.django import DjangoModelFactory

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    name = factory.Faker("name")
    email = factory.Faker("email")

# Async helper
async def acreate_user(**kwargs):
    """Async wrapper for factory."""
    from asgiref.sync import sync_to_async
    return await sync_to_async(UserFactory.create)(**kwargs)
```

```python
# test_with_factory.py
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_with_factory():
    user = await acreate_user(name="FactoryUser")

    fetched = await User.objects.aget(id=user.id)
    assert fetched.name == "FactoryUser"
```

## Common Django Async Fixtures

```python
# conftest.py
import pytest
import pytest_asyncio
from django.test import AsyncClient

@pytest.fixture
def async_client():
    return AsyncClient()

@pytest_asyncio.fixture
async def authenticated_async_client(async_client):
    user = await User.objects.acreate(
        username="testuser",
        email="test@example.com"
    )
    await sync_to_async(async_client.force_login)(user)
    return async_client

@pytest_asyncio.fixture
async def sample_users():
    users = []
    for i in range(3):
        user = await User.objects.acreate(
            name=f"User {i}",
            email=f"user{i}@example.com"
        )
        users.append(user)
    yield users
    # Cleanup
    for user in users:
        await user.adelete()
```

## Troubleshooting Django Async Tests

### "SynchronousOnlyOperation" Error

Django raises this when sync ORM is called from async context.

```python
# ❌ Wrong - using sync ORM in async test
@pytest.mark.asyncio
async def test_wrong():
    user = User.objects.get(id=1)  # SynchronousOnlyOperation!

# ✅ Correct - use async ORM
@pytest.mark.asyncio
async def test_correct():
    user = await User.objects.aget(id=1)
```

### Database Not Available

Ensure `transaction=True` for async tests:

```python
# ❌ May fail
@pytest.mark.django_db
async def test_without_transaction():
    ...

# ✅ Works
@pytest.mark.django_db(transaction=True)
async def test_with_transaction():
    ...
```

### Mixing Sync and Async

Use `sync_to_async` for sync code in async context:

```python
from asgiref.sync import sync_to_async

@pytest.mark.asyncio
async def test_mixed():
    # Wrap sync function
    result = await sync_to_async(sync_function)()

    # Wrap sync ORM (if needed)
    users = await sync_to_async(list)(User.objects.all())
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Async view test | `@pytest.mark.asyncio` + `@pytest.mark.django_db(transaction=True)` |
| Async ORM | Use `aget()`, `acreate()`, `aupdate()`, `adelete()` |
| Async iteration | `async for item in queryset` |
| WebSocket test | `WebsocketCommunicator` from channels.testing |
| Mix sync/async | `sync_to_async()` from asgiref |
| Async client | `django.test.AsyncClient` (Django 4.1+) |
