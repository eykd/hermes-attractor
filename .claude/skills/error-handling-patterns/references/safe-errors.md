# Safe Error Messages

## Principles

1. **No sensitive data**: API keys, passwords, tokens, user data
2. **No implementation details**: File paths, SQL queries, stack traces (in production)
3. **User-friendly language**: Actionable, clear, helpful

## Common Leaks to Avoid

### File Paths

```python
# ❌ Bad - exposes internal paths
raise StorageError(f"Failed to save to /home/user/.hermes_attractor/secrets/api_key.json")

# ✅ Good - generic location
raise StorageError("Failed to save artifact to storage")

# ✅ Better - safe filename only
raise StorageError(f"Failed to save {artifact.name}")
```

### Database Queries

```python
# ❌ Bad - exposes schema
raise ValidationError(
    f"Query failed: SELECT * FROM users WHERE email='{email}'"
)

# ✅ Good - generic message
raise ValidationError("Invalid user credentials")
```

### API Keys / Tokens

```python
# ❌ Bad - includes token
raise ConfigurationError(f"Invalid API key: sk-1234567890abcdef")

# ✅ Good - no sensitive data
raise ConfigurationError("Invalid API key format")
```

### Stack Traces (Production)

```python
# ❌ Bad - full stack trace to user
@click.command()
def create(title: str) -> None:
    try:
        create_concept(title)
    except Exception as e:
        click.echo(f"Error: {e}\n{traceback.format_exc()}")  # Too much!

# ✅ Good - user-friendly message
@click.command()
def create(title: str) -> None:
    try:
        create_concept(title)
    except ValidationError as e:
        click.echo(f"Error: {e}", err=True)
    except HermesAttractorError as e:
        click.echo(f"Unexpected error: {e}", err=True)
        logger.exception("Unexpected error")  # Log full details
```

## User-Friendly Messages

### Be Specific (Without Exposing Details)

```python
# ❌ Bad - too vague
raise ValidationError("Invalid input")

# ✅ Good - specific without details
raise ValidationError("Title must be between 1 and 100 characters")
```

### Provide Actionable Guidance

```python
# ❌ Bad - what should user do?
raise ConfigurationError("API key missing")

# ✅ Good - tells user what to do
raise ConfigurationError(
    "API key not configured. Set HERMES_ATTRACTOR_API_KEY environment variable."
)
```

### Use Domain Language

```python
# ❌ Bad - technical jargon
raise StorageError("I/O operation failed on filesystem layer")

# ✅ Good - domain language
raise StorageError("Unable to save concept to disk")
```

## Context Without Leaking

Safe context to include:
- Operation being performed
- Field names (if not sensitive)
- Constraint violations
- Expected formats

Unsafe context to exclude:
- Actual values (unless known safe)
- File system paths
- Database schemas
- API endpoints

```python
# ✅ Good - safe context
@dataclass
class ValidationError(HermesAttractorError):
    field: str
    constraint: str

    def __str__(self) -> str:
        return f"{self.field}: {self.constraint}"

# Usage
raise ValidationError(
    field="title",
    constraint="must be between 1 and 100 characters",
)
# Message: "title: must be between 1 and 100 characters"
```

## Logging vs User Messages

**User messages**: Simple, safe, actionable
**Log messages**: Detailed, can include sensitive data (if logs secured)

```python
import logging

logger = logging.getLogger(__name__)

def save_concept(concept: Concept, path: Path) -> None:
    try:
        path.write_text(concept.to_json())
    except OSError as e:
        # Detailed log (secured)
        logger.error(
            f"Failed to save concept to {path}: {e}",
            exc_info=True,
        )
        # Simple user message
        raise StorageError(f"Failed to save {concept.title}")
```

## Error Message Testing

Test that error messages don't leak:

```python
def test_storage_error_no_path_leak() -> None:
    """StorageError doesn't expose file paths."""
    with pytest.raises(StorageError) as exc_info:
        save_concept(concept, Path("/secrets/api_key.json"))

    error_msg = str(exc_info.value)
    assert "/secrets" not in error_msg
    assert "api_key" not in error_msg
```

## References

- OWASP: Improper Error Handling
- Security logging best practices
