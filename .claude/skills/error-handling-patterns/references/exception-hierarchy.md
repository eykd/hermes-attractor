# Exception Hierarchy

## Base Exception

All hermes_attractor exceptions inherit from a common base:

```python
class HermesAttractorError(Exception):
    """Base exception for all hermes_attractor errors."""
```

## Domain Exceptions

Create specific exceptions for domain errors:

```python
class ValidationError(HermesAttractorError):
    """Validation failed for domain object."""

class StageError(HermesAttractorError):
    """Error in story stage processing."""

class StorageError(HermesAttractorError):
    """Error accessing storage."""

class ConfigurationError(HermesAttractorError):
    """Error in application configuration."""
```

## Catching Exceptions

**Specific exceptions first:**

```python
# ✅ Good - specific to general
try:
    process_concept()
except ValidationError as e:
    handle_validation_error(e)
except StageError as e:
    handle_stage_error(e)
except HermesAttractorError as e:
    handle_generic_hermes_attractor_error(e)

# ❌ Bad - too broad
try:
    process_concept()
except Exception as e:  # Catches SystemExit, KeyboardInterrupt!
    handle_error(e)
```

## Exception Context

Add useful context without exposing sensitive data:

```python
# ✅ Good - structured context
@dataclass
class ValidationError(HermesAttractorError):
    field: str
    constraint: str
    attempted_value: str | None = None  # Optional

    def __str__(self) -> str:
        msg = f"{self.field} validation failed: {self.constraint}"
        if self.attempted_value:
            # Truncate to avoid exposing too much
            safe_value = self.attempted_value[:50]
            msg += f" (value: '{safe_value}...')"
        return msg

# Usage
raise ValidationError(
    field="title",
    constraint="must be between 1 and 100 characters",
    attempted_value=title,
)
```

## Exception Chaining

Preserve exception context with `from`:

```python
# ✅ Good - preserve original exception
try:
    data = json.loads(raw_data)
except json.JSONDecodeError as e:
    raise ValidationError("Invalid concept JSON") from e
    # Original exception available in __cause__

# ❌ Bad - loses context
try:
    data = json.loads(raw_data)
except json.JSONDecodeError:
    raise ValidationError("Invalid concept JSON")  # Lost original!
```

## Custom Exception Methods

Add helper methods for common patterns:

```python
class StorageError(HermesAttractorError):
    """Error accessing storage."""

    def __init__(self, message: str, path: Path | None = None) -> None:
        super().__init__(message)
        self.path = path

    @classmethod
    def file_not_found(cls, path: Path) -> "StorageError":
        """Create exception for missing file."""
        return cls(f"File not found: {path.name}", path=path)

    @classmethod
    def permission_denied(cls, path: Path) -> "StorageError":
        """Create exception for permission error."""
        return cls(f"Permission denied: {path.name}", path=path)

# Usage
raise StorageError.file_not_found(concept_path)
```

## When to Create New Exception

Create new exception class when:
- Different handling needed for this error type
- Grouping related errors under common parent
- Adding structured context fields

Don't create when:
- Existing exception type is sufficient
- Just changing the message (reuse existing exception)

## References

- hermes_attractor.domain.exceptions - Domain exception hierarchy
- PEP 3134: Exception Chaining
