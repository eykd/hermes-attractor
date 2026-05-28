# Error Handling Patterns

## Exception Hierarchy

**Create domain-specific exception hierarchy:**

```python
# Base exception
class HermesAttractorError(Exception):
    """Base exception for all hermes_attractor errors."""

# Domain-specific exceptions
class ValidationError(HermesAttractorError):
    """Validation failed for domain object."""

class StageError(HermesAttractorError):
    """Error in story stage processing."""

class StorageError(HermesAttractorError):
    """Error accessing storage."""

# Usage
def validate_concept(concept: Concept) -> None:
    if not concept.title:
        raise ValidationError("Title required")
```

## Validate at Boundaries

**Only validate at system boundaries:**

```python
# ✅ Good - validate at CLI boundary
@click.command()
def create_concept(title: str) -> None:
    if not title.strip():  # User input validation
        click.echo("Error: Title required")
        raise click.Abort()

    concept = Concept(Title(title))  # Already validated

# ❌ Bad - re-validating everywhere
def use_case_execute(title: str) -> None:
    if not title.strip():  # Redundant
        raise ValidationError("Title required")

def domain_save(title: str) -> None:
    if not title.strip():  # Redundant again
        raise ValidationError("Title required")
```

## Result Types (Expected Failures)

**Use Result for expected failures, exceptions for unexpected:**

```python
from typing import Union
from dataclasses import dataclass

@dataclass
class Success[T]:
    value: T

@dataclass
class Failure:
    error: str

Result = Union[Success[T], Failure]

# Expected failure - use Result
def parse_concept(data: str) -> Result[Concept]:
    try:
        parsed = json.loads(data)
        return Success(Concept(**parsed))
    except (json.JSONDecodeError, KeyError) as e:
        return Failure(f"Parse failed: {e}")

# Unexpected failure - use exception
def load_from_disk(path: Path) -> Concept:
    if not path.exists():
        raise StorageError(f"File not found: {path}")
    ...
```

## Safe Error Messages

**Never expose sensitive data in errors:**

```python
# ❌ Bad - leaks implementation details
raise StorageError(f"Failed to save to /home/user/.secrets/api_key.json")

# ✅ Good - safe for users
raise StorageError("Failed to save artifact")

# ❌ Bad - exposes SQL structure
raise ValidationError(f"Query failed: SELECT * FROM users WHERE password='{pw}'")

# ✅ Good - generic message
raise ValidationError("Invalid credentials")
```

## Error Context

**Provide useful context without sensitive data:**

```python
# ✅ Good - helpful context
raise ValidationError(
    f"Concept validation failed: title='{concept.title[:20]}...' "
    f"stage={concept.stage.value}"
)

# ✅ Good - structured context
@dataclass
class ValidationError(HermesAttractorError):
    field: str
    value: str
    constraint: str

    def __str__(self) -> str:
        return f"{self.field} validation failed: {self.constraint}"
```

## Resource Cleanup

**Use context managers for safe cleanup:**

```python
# ✅ Good - guaranteed cleanup
from contextlib import contextmanager

@contextmanager
def open_artifact_file(path: Path):
    f = open(path, "w")
    try:
        yield f
    finally:
        f.close()  # Always closes

# Usage
with open_artifact_file(path) as f:
    write_artifact(f, concept)
```

## References

- hermes_attractor.domain.exceptions - Domain exception hierarchy
- PEP 3134: https://peps.python.org/pep-3134/ (Exception chaining)
- /error-handling-patterns skill - Detailed patterns
