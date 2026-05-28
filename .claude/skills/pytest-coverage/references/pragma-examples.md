# Pragma Usage Patterns

Detailed examples for `# pragma: no cover` and `# pragma: no branch`.

## `# pragma: no cover` — Exclude Entire Blocks

### Scope Behavior

When placed on a line introducing a block, excludes the **entire block**:

```python
def debug_info():  # pragma: no cover
    # ALL of this is excluded:
    print("Starting debug")
    log_state()
    dump_variables()
    return debug_data
```

```python
class LegacyHandler:  # pragma: no cover
    # Entire class excluded
    def handle(self): ...
    def process(self): ...
```

### Pattern 1: Debug/Development Code

```python
def process_order(order):
    result = calculate_total(order)

    if settings.DEBUG:  # pragma: no cover
        print(f"Order {order.id}: total={result}")
        log_order_details(order)

    return result
```

### Pattern 2: Debugging Methods

```python
class Order:
    def __init__(self, items):
        self.items = items
        self.total = sum(item.price for item in items)

    def __repr__(self):  # pragma: no cover
        return f"Order(items={len(self.items)}, total={self.total})"

    def __str__(self):  # pragma: no cover
        return f"Order #{self.id}: ${self.total:.2f}"
```

**Better**: Use config pattern `exclude_also = ["def __repr__", "def __str__"]`

### Pattern 3: Abstract Methods

```python
from abc import ABC, abstractmethod

class BaseProcessor(ABC):
    @abstractmethod
    def process(self, data):  # pragma: no cover
        """Subclasses must implement."""
        raise NotImplementedError

    @abstractmethod
    def validate(self, data):  # pragma: no cover
        ...
```

**Better**: Use config pattern `exclude_also = ["@(abc\\.)?abstractmethod", "^\\s*\\.\\.\\.$"]`

### Pattern 4: Platform-Specific Code

```python
import sys

def get_config_path():
    if sys.platform == "win32":  # pragma: no cover
        return Path(os.environ["APPDATA"]) / "myapp"
    elif sys.platform == "darwin":  # pragma: no cover
        return Path.home() / "Library" / "Application Support" / "myapp"
    else:
        return Path.home() / ".config" / "myapp"
```

Comment explaining why:
```python
    # Windows-specific: CI runs on Linux
    if sys.platform == "win32":  # pragma: no cover
```

### Pattern 5: Main Entry Points

```python
def main():
    app = create_app()
    app.run()

if __name__ == "__main__":  # pragma: no cover
    main()
```

**Better**: Use config pattern `exclude_also = ["if __name__ == .__main__.:"]`

### Pattern 6: Type Checking Imports

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from heavy_module import ExpensiveClass
    from another_module import TypeOnlyClass
```

**Note**: coverage.py 7.10+ excludes `TYPE_CHECKING` blocks automatically.

### Pattern 7: Defensive Unreachable Code

```python
def divide_validated(a: float, b: float) -> float:
    """Caller guarantees b != 0 via validation."""
    # Defensive check for violated invariant
    if b == 0:  # pragma: no cover
        raise RuntimeError("Invariant violated: b must be non-zero")
    return a / b
```

Always add a comment explaining why it's unreachable.

### Pattern 8: Error Handling for Rare System Errors

```python
def read_config(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON: {e}") from e
    except PermissionError:  # pragma: no cover
        # Filesystem permissions hard to test reliably
        raise ConfigError(f"Cannot read {path}: permission denied")
```

### Pattern 9: Legacy Code Pending Removal

```python
def new_algorithm(data):
    return optimized_process(data)

def legacy_algorithm(data):  # pragma: no cover
    """Deprecated: Remove in v3.0. Use new_algorithm()."""
    return slow_legacy_process(data)
```

---

## `# pragma: no branch` — Accept Partial Branches

### When to Use

The line IS covered, but one branch path intentionally never executes.

### Pattern 1: Infinite/Event Loops

```python
def wait_for_completion(timeout: float) -> bool:
    """Wait for task, return True if completed."""
    deadline = time.time() + timeout
    while time.time() < deadline:  # pragma: no branch
        if task.is_complete():
            return True
        time.sleep(0.1)
    return False
```

The `while` loop exits via `return True` or timeout, never naturally.

### Pattern 2: Search Loops That Usually Find

```python
def find_handler(event_type: str) -> Handler:
    """Find handler for event type."""
    for handler in self.handlers:  # pragma: no branch
        if handler.can_handle(event_type):
            return handler
    raise NoHandlerError(f"No handler for {event_type}")
```

If tests always find a handler, the "loop exhausted" path isn't taken.

### Pattern 3: Retry Loops

```python
def fetch_with_retry(url: str, max_attempts: int = 3) -> Response:
    for attempt in range(max_attempts):  # pragma: no branch
        try:
            return requests.get(url, timeout=10)
        except RequestException:
            if attempt == max_attempts - 1:
                raise
            time.sleep(2 ** attempt)
```

### Pattern 4: Consumer Loops

```python
def process_queue(queue: Queue) -> None:
    while True:  # pragma: no branch
        item = queue.get()
        if item is SHUTDOWN_SENTINEL:
            return
        process(item)
```

### Pattern 5: Feature Flags

```python
def calculate_score(data):
    score = base_calculation(data)

    if feature_flags.is_enabled("enhanced_scoring"):  # pragma: no branch
        # Always enabled in test environment
        score = apply_enhancements(score)

    return score
```

---

## Key Differences Summary

| Scenario | Use | Effect |
|----------|-----|--------|
| Entire function untestable | `no cover` on `def` | Function excluded |
| Entire class untestable | `no cover` on `class` | Class excluded |
| One branch untestable | `no cover` on branch | Branch + block excluded |
| Branch intentionally partial | `no branch` on conditional | Line covered, partial OK |
| Loop that always breaks | `no branch` on loop | Line covered, no-exit OK |

---

## Documenting Pragmas

Always explain WHY code is excluded:

```python
# Good: Explains the reason
if sys.platform == "win32":  # pragma: no cover  # CI runs Linux
    ...

# Bad: No explanation
if sys.platform == "win32":  # pragma: no cover
    ...
```

---

## Code Review Checklist

When reviewing pragmas, ask:

1. **Can this code be tested?** — If yes, write tests instead
2. **Is the exclusion justified?** — Platform, debug-only, abstract?
3. **Is there a better design?** — More testable architecture?
4. **Is it the right pragma?** — `no cover` vs `no branch`?
5. **Is it documented?** — Comment explaining why?
6. **Could config handle it?** — `exclude_also` pattern instead?
