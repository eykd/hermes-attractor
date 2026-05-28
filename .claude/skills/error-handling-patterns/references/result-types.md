# Result Types

## The Result Pattern

Result type makes success/failure explicit in the type system:

```python
from typing import Union, TypeVar, Generic
from dataclasses import dataclass

T = TypeVar("T")

@dataclass
class Success(Generic[T]):
    """Successful result with value."""
    value: T

@dataclass
class Failure:
    """Failed result with error message."""
    error: str

# Result is either Success or Failure
Result = Success[T] | Failure
```

## When to Use Result

**Use Result for expected failures:**
- Parsing input (may be malformed)
- Validation (may fail)
- File operations (file may not exist)
- Any operation where failure is a valid outcome

**Use Exception for unexpected failures:**
- Programming errors (bugs)
- System failures (out of memory)
- Invariant violations

## Basic Usage

```python
def parse_concept(data: str) -> Result[Concept]:
    """Parse concept from JSON string."""
    try:
        parsed = json.loads(data)
        concept = Concept(**parsed)
        return Success(concept)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return Failure(f"Failed to parse concept: {e}")

# Using the result
result = parse_concept(user_input)
match result:
    case Success(concept):
        print(f"Loaded: {concept.title}")
    case Failure(error):
        print(f"Error: {error}")
```

## Railway-Oriented Programming

Chain operations that return Result:

```python
def parse_concept(data: str) -> Result[Concept]:
    ...

def validate_concept(concept: Concept) -> Result[Concept]:
    if not concept.title:
        return Failure("Title required")
    if len(concept.title) > 100:
        return Failure("Title too long")
    return Success(concept)

def save_concept(concept: Concept) -> Result[Path]:
    try:
        path = Path(f"{concept.title}.json")
        path.write_text(concept.to_json())
        return Success(path)
    except OSError as e:
        return Failure(f"Failed to save: {e}")

# Chain operations
def process_concept_data(data: str) -> Result[Path]:
    result = parse_concept(data)
    match result:
        case Success(concept):
            validation_result = validate_concept(concept)
            match validation_result:
                case Success(valid_concept):
                    return save_concept(valid_concept)
                case Failure(error):
                    return Failure(error)
        case Failure(error):
            return Failure(error)
```

## Helper Functions

Make chaining easier with helper functions:

```python
def and_then(
    result: Result[T],
    func: Callable[[T], Result[U]],
) -> Result[U]:
    """Chain Result-returning functions."""
    match result:
        case Success(value):
            return func(value)
        case Failure(error):
            return Failure(error)

def map_result(
    result: Result[T],
    func: Callable[[T], U],
) -> Result[U]:
    """Transform successful value."""
    match result:
        case Success(value):
            return Success(func(value))
        case Failure(error):
            return Failure(error)

# Cleaner chaining
def process_concept_data(data: str) -> Result[Path]:
    return and_then(
        and_then(
            parse_concept(data),
            validate_concept,
        ),
        save_concept,
    )
```

## Result with Context

Add context to failures:

```python
@dataclass
class Failure:
    """Failed result with error and context."""
    error: str
    context: dict[str, str] | None = None

# Usage
def validate_concept(concept: Concept) -> Result[Concept]:
    if not concept.title:
        return Failure(
            "Validation failed",
            context={"field": "title", "constraint": "required"},
        )
    return Success(concept)
```

## Alternative: returns Library

For production, consider the `returns` library:

```python
from returns.result import Result, Success, Failure

def parse_concept(data: str) -> Result[Concept, str]:
    ...

# Provides .bind(), .map(), .alt() methods
result = (
    parse_concept(data)
    .bind(validate_concept)
    .bind(save_concept)
)
```

## CLI Integration

Convert Result to CLI exit codes:

```python
@click.command()
def create(title: str) -> None:
    result = create_concept_from_title(title)
    match result:
        case Success(concept):
            click.echo(f"Created: {concept.title}")
        case Failure(error):
            click.echo(f"Error: {error}", err=True)
            raise click.Abort()  # Exit code 1
```

## References

- returns library: https://github.com/dry-python/returns
- Railway Oriented Programming: https://fsharpforfunandprofit.com/rop/
