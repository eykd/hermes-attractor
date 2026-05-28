# Operation Context Management

**Purpose**: `contextvars` patterns for operation correlation and trace context propagation.

## When to Use

Use this reference when implementing operation context management with `contextvars` to automatically correlate logs across a call stack (and across `await` points in async code). This propagates `request_id` and `trace_id` without threading them through every function signature.

`contextvars.ContextVar` is the Python equivalent of an async-local store: each `asyncio` task and each thread sees its own value, and values set inside a `with`-scoped token are restored on exit.

## Pattern

```python
# src/hermes_attractor/adapters/logging/context.py
from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from time import monotonic
from typing import Iterator

_context: ContextVar["OperationContext | None"] = ContextVar("operation_context", default=None)


@dataclass(frozen=True, slots=True)
class OperationContext:
    request_id: str
    trace_id: str | None = None
    span_id: str | None = None
    user_id: str | None = None
    start_time: float = 0.0


def get_context() -> OperationContext | None:
    return _context.get()


def generate_request_id() -> str:
    return str(uuid.uuid4())


@contextmanager
def run_with_context(context: OperationContext) -> Iterator[OperationContext]:
    """Bind ``context`` for the duration of the ``with`` block, then restore."""
    token = _context.set(context)
    try:
        yield context
    finally:
        _context.reset(token)


def extract_trace_context(headers: dict[str, str]) -> tuple[str, str]:
    """Parse or generate W3C trace context (``traceparent`` header)."""
    traceparent = headers.get("traceparent")
    if traceparent:
        parts = traceparent.split("-")
        if len(parts) >= 3:
            return parts[1], parts[2]
    return uuid.uuid4().hex, uuid.uuid4().hex[:16]
```

## Example Usage

```python
# Entry point (e.g. a plugin command handler or CLI dispatch)
from hermes_attractor.adapters.logging import create_application_logger
from hermes_attractor.adapters.logging.context import (
    OperationContext,
    extract_trace_context,
    generate_request_id,
    run_with_context,
)


def handle_request(headers: dict[str, str], method: str, path: str) -> Response:
    request_id = headers.get("x-request-id") or generate_request_id()
    trace_id, span_id = extract_trace_context(headers)

    context = OperationContext(
        request_id=request_id,
        trace_id=trace_id,
        span_id=span_id,
        start_time=monotonic(),
    )

    with run_with_context(context):
        logger = create_application_logger(
            service="api", environment="production", version="1.0.0",
        )
        logger.info(
            "request received",
            extra={"event": "http.request.received",
                   "fields": {"http_method": method, "http_path": path}},
        )

        response = dispatch(method, path)

        logger.info(
            "response sent",
            extra={"event": "http.response.sent",
                   "fields": {"http_status": response.status,
                              "duration_ms": round((monotonic() - context.start_time) * 1000)}},
        )
        return response
```

## Edge Cases

### Nested Operation Contexts

**Scenario**: Calling a sub-operation that needs its own span while preserving correlation
**Solution**: Derive a child context from the parent, keeping `request_id`/`trace_id` but minting a new `span_id`.

```python
import uuid

def child_context() -> OperationContext:
    parent = get_context()
    return OperationContext(
        request_id=parent.request_id if parent else generate_request_id(),
        trace_id=parent.trace_id if parent else None,
        span_id=uuid.uuid4().hex[:16],  # new span
        start_time=monotonic(),
    )
```

### Context Loss Across Threads or Background Tasks

**Scenario**: Handing work to a `ThreadPoolExecutor` or a background queue loses the `ContextVar`.
**Solution**: Capture and re-bind explicitly. For threads, use `contextvars.copy_context().run(...)`. For queues, serialize correlation IDs into the message and re-establish on consumption.

```python
import contextvars

ctx = contextvars.copy_context()
executor.submit(ctx.run, do_work, payload)

# Queue producer/consumer:
message = {"data": payload, "request_id": (c := get_context()) and c.request_id}
# On consume:
with run_with_context(OperationContext(request_id=message["request_id"], start_time=monotonic())):
    process(message["data"])
```

## Common Mistakes

### ❌ Mistake: Reading the ContextVar without binding it

Calling `get_context()` outside a `run_with_context` block returns `None`.

```python
# Bad: no context bound
def handle_request() -> Response:
    logger = create_logger(...)  # get_context() returns None → request_id "no-context"
    return dispatch()
```

### ✅ Correct: Wrap the handler in run_with_context

```python
# Good: context established for the whole operation
def handle_request() -> Response:
    ctx = OperationContext(request_id=generate_request_id(), start_time=monotonic())
    with run_with_context(ctx):
        return dispatch()
```

### ❌ Mistake: Mutating a shared context object

`OperationContext` is frozen for a reason — mutation would leak across concurrent tasks if you shared an instance.

```python
# Bad: mutating shared state
ctx = get_context()
ctx.user_id = "user-123"  # frozen dataclass → AttributeError (and would be unsafe anyway)
```

### ✅ Correct: Bind a new context for changes

```python
# Good: immutable update via dataclasses.replace
import dataclasses

current = get_context()
updated = dataclasses.replace(current, user_id="user-123")
with run_with_context(updated):
    ...
```

## Testing

```python
# tests/unit/adapters/logging/test_context.py
import asyncio

from hermes_attractor.adapters.logging.context import (
    OperationContext,
    get_context,
    run_with_context,
)


def test_context_available_within_scope():
    with run_with_context(OperationContext(request_id="test-123")):
        ctx = get_context()
        assert ctx is not None
        assert ctx.request_id == "test-123"


def test_context_cleared_after_scope():
    with run_with_context(OperationContext(request_id="test-123")):
        pass
    assert get_context() is None


def test_contexts_isolated_across_async_tasks():
    results: list[str] = []

    async def worker(request_id: str, delay: float) -> None:
        with run_with_context(OperationContext(request_id=request_id)):
            await asyncio.sleep(delay)
            ctx = get_context()
            assert ctx is not None
            results.append(ctx.request_id)

    async def main() -> None:
        await asyncio.gather(worker("req-1", 0.01), worker("req-2", 0.005))

    asyncio.run(main())
    assert set(results) == {"req-1", "req-2"}
```

## Related References

- [logger-factory.md](./logger-factory.md) - Using context in logger creation
- [base-fields.md](./base-fields.md) - Context fields in the `BaseLogFields` schema
