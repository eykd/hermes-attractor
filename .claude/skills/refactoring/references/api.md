# API Refactorings

## Introduce Parameter Object

**When**: Functions have too many parameters

```python
# Before - parameter soup
def create_concept(
    title: str,
    logline: str,
    genre: str,
    author: str,
    created: datetime,
    modified: datetime,
    word_count: int,
) -> Concept:
    ...

# After - parameter object
@dataclass(frozen=True)
class ConceptParams:
    title: str
    logline: str
    genre: str
    author: str
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    word_count: int = 0

def create_concept(params: ConceptParams) -> Concept:
    ...

# Caller
create_concept(ConceptParams(
    title="My Story",
    logline="A great story",
    genre="SciFi",
    author="John Doe",
))
```

## Replace Boolean Parameter with Enum

**When**: Boolean flag controls behavior

```python
# Before - unclear boolean
def format_concept(concept: Concept, verbose: bool) -> str:
    if verbose:
        return f"{concept.title}: {concept.logline} ({concept.genre})"
    else:
        return concept.title

# Caller
format_concept(concept, True)  # True means what?

# After - explicit enum
from enum import Enum, auto

class FormatStyle(Enum):
    BRIEF = auto()
    DETAILED = auto()

def format_concept(concept: Concept, style: FormatStyle) -> str:
    if style == FormatStyle.DETAILED:
        return f"{concept.title}: {concept.logline} ({concept.genre})"
    else:
        return concept.title

# Caller
format_concept(concept, FormatStyle.DETAILED)  # Clear intent
```

## Remove Flag Argument

**When**: Function does different things based on flag

```python
# Before - function does two things
def process_concept(concept: Concept, save: bool) -> Concept:
    validated = validate_concept(concept)
    if save:
        storage.save(validated)
    return validated

# After - split into focused functions
def validate_concept(concept: Concept) -> Concept:
    # Just validation
    ...

def validate_and_save_concept(concept: Concept) -> Concept:
    validated = validate_concept(concept)
    storage.save(validated)
    return validated
```

## Decompose Complex Parameter

**When**: Parameter is complex structure only partially used

```python
# Before - uses small part of large object
def get_author_name(concept: Concept) -> str:
    return concept.metadata.author.name  # Only uses one field

# After - ask for what you need
def get_author_name(author: Author) -> str:
    return author.name

# Or even simpler
def get_name(author: Author) -> str:
    return author.name

# Caller
author_name = get_name(concept.metadata.author)
```

## Replace Return Code with Exception

**When**: Using error codes instead of exceptions

```python
# Before - error code pattern
def validate_concept(concept: Concept) -> int:
    if not concept.title:
        return -1  # What does -1 mean?
    if not concept.logline:
        return -2  # What does -2 mean?
    return 0  # Success?

# Caller must check
result = validate_concept(concept)
if result != 0:
    handle_error(result)  # Decode error code

# After - exceptions
def validate_concept(concept: Concept) -> None:
    if not concept.title:
        raise ValidationError("Title required")
    if not concept.logline:
        raise ValidationError("Logline required")

# Caller
try:
    validate_concept(concept)
except ValidationError as e:
    handle_error(e)  # Clear error message
```

## Replace Exception with Result Type

**When**: Failure is expected and part of normal flow

```python
# Before - exceptions for expected cases
def parse_concept(data: str) -> Concept:
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        raise ConceptParseError("Invalid JSON")

# Caller
try:
    concept = parse_concept(data)
    # ... handle success
except ConceptParseError:
    # ... handle failure

# After - Result type for expected failures
from typing import Union
from dataclasses import dataclass

@dataclass
class Success[T]:
    value: T

@dataclass
class Failure:
    error: str

Result = Union[Success[T], Failure]

def parse_concept(data: str) -> Result[Concept]:
    try:
        concept = json.loads(data)
        return Success(concept)
    except json.JSONDecodeError as e:
        return Failure(f"Invalid JSON: {e}")

# Caller
result = parse_concept(data)
match result:
    case Success(concept):
        # ... handle success
    case Failure(error):
        # ... handle failure
```
