# Data Refactorings

## Replace Mutable with Immutable

**When**: Shared mutable state causes bugs

```python
# Before - mutable default argument (bug!)
def add_tag(tag: str, tags: list[str] = []) -> list[str]:
    tags.append(tag)  # Modifies shared default!
    return tags

tags1 = add_tag("concept")  # ["concept"]
tags2 = add_tag("premise")  # ["concept", "premise"] - Oops!

# After - immutable pattern
def add_tag(tag: str, tags: list[str] | None = None) -> list[str]:
    if tags is None:
        tags = []
    return tags + [tag]  # Returns new list

# Better - use tuple (immutable)
def add_tag(tag: str, tags: tuple[str, ...] = ()) -> tuple[str, ...]:
    return tags + (tag,)
```

## Use Dataclass for Value Objects

**When**: Many `__init__` parameters or equality logic

```python
# Before - manual implementation
class Title:
    def __init__(self, value: str) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Title):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

# After - dataclass
from dataclasses import dataclass

@dataclass(frozen=True)  # Immutable
class Title:
    value: str
    # __eq__, __hash__, __repr__ auto-generated
```

## Replace Nested Structures with Objects

**When**: Deep nesting makes code hard to read

```python
# Before - nested dicts
concept = {
    "metadata": {
        "created": "2024-01-01",
        "author": {
            "name": "John Doe",
            "email": "john@example.com",
        },
    },
    "content": {
        "title": "My Story",
        "logline": "A story about stories",
    },
}

# Hard to access
author_name = concept["metadata"]["author"]["name"]

# After - structured objects
@dataclass(frozen=True)
class Author:
    name: str
    email: str

@dataclass(frozen=True)
class Metadata:
    created: str
    author: Author

@dataclass(frozen=True)
class Content:
    title: str
    logline: str

@dataclass(frozen=True)
class Concept:
    metadata: Metadata
    content: Content

# Easy to access, type-safe
author_name = concept.metadata.author.name
```

## Split Large Data Structure

**When**: Data structure has too many fields

```python
# Before - too many fields
@dataclass
class Concept:
    title: str
    logline: str
    genre: str
    author_name: str
    author_email: str
    created_at: datetime
    modified_at: datetime
    word_count: int
    target_audience: str
    # ... 20 more fields

# After - split into cohesive groups
@dataclass(frozen=True)
class Author:
    name: str
    email: str

@dataclass(frozen=True)
class Metadata:
    created_at: datetime
    modified_at: datetime
    word_count: int
    target_audience: str

@dataclass(frozen=True)
class Concept:
    title: str
    logline: str
    genre: str
    author: Author
    metadata: Metadata
```

## Replace List with Typed Collection

**When**: List elements have specific meaning

```python
# Before - list with positional meaning
def get_concept_info() -> list[str]:
    return ["Title", "SciFi", "John Doe"]  # What's what?

title, genre, author = get_concept_info()  # Easy to mix up

# After - named tuple or dataclass
from typing import NamedTuple

class ConceptInfo(NamedTuple):
    title: str
    genre: str
    author: str

def get_concept_info() -> ConceptInfo:
    return ConceptInfo("Title", "SciFi", "John Doe")

info = get_concept_info()
title = info.title  # Clear and type-safe
```
