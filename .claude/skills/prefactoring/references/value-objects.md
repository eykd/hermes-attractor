# Value Objects

## Wrap Primitives

**Never use raw primitives for domain concepts:**

```python
# ❌ Bad - primitive obsession
def create_concept(title: str, genre: str) -> Concept:
    if not title:  # Validation scattered everywhere
        raise ValidationError("Title required")
    ...

# ✅ Good - domain value objects
@dataclass(frozen=True)
class Title:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValidationError("Title cannot be empty")

def create_concept(title: Title, genre: Genre) -> Concept:
    # Validation already done, safe to use
    ...
```

## Pydantic Models

For complex validation, use Pydantic:

```python
from pydantic import BaseModel, field_validator

class Concept(BaseModel):
    title: str
    logline: str
    genre: str

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

    model_config = {"frozen": True}  # Immutability
```

## Dataclass vs Pydantic

**Use dataclass when:**
- Simple types with basic validation
- Performance critical (dataclass is faster)
- No JSON serialization needed

**Use Pydantic when:**
- Complex validation rules
- JSON/dict serialization required
- Type coercion needed (str → int, etc.)

## Immutability

**Always prefer immutable value objects:**

```python
# Dataclass
@dataclass(frozen=True)
class Title:
    value: str

# Pydantic
class Title(BaseModel):
    value: str
    model_config = {"frozen": True}
```

## Identity vs Equality

**Entities**: Identity matters (same ID = same entity)
**Value Objects**: Equality by value (same content = same object)

```python
# Entity (has identity)
@dataclass
class Story:
    id: StoryId
    title: Title

# Value Object (no identity)
@dataclass(frozen=True)
class Title:
    value: str
```

## References

- hermes_attractor.domain.* - Domain value object examples
- Pydantic docs: https://docs.pydantic.dev
