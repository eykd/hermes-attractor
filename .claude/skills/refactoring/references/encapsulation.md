# Encapsulation Refactorings

## Encapsulate Field

**When**: Direct access to attributes allows invalid state

```python
# Before - public attributes
class Concept:
    def __init__(self, title: str) -> None:
        self.title = title  # Can be set to anything!

concept = Concept("Valid")
concept.title = ""  # Oops! Invalid state

# After - property with validation
class Concept:
    def __init__(self, title: str) -> None:
        self._title = title
        self._validate_title()

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        self._title = value
        self._validate_title()

    def _validate_title(self) -> None:
        if not self._title.strip():
            raise ValidationError("Title cannot be empty")
```

## Hide Data, Expose Behavior

**When**: Clients manipulate object data directly

```python
# Before - data-focused (anemic domain model)
@dataclass
class Concept:
    title: str
    stage: Stage

# Client does the work
def advance_concept(concept: Concept) -> None:
    if concept.stage == Stage.CONCEPT:
        concept.stage = Stage.PREMISE  # Client knows stage order

# After - behavior-focused (rich domain model)
@dataclass
class Concept:
    title: str
    stage: Stage

    def advance_to_next_stage(self) -> None:
        """Advance to the next stage in the pipeline."""
        self.stage = self._next_stage()  # Concept knows its own logic

    def _next_stage(self) -> Stage:
        stage_order = [Stage.CONCEPT, Stage.PREMISE, Stage.THEME, ...]
        current_index = stage_order.index(self.stage)
        return stage_order[current_index + 1]

# Client just asks
concept.advance_to_next_stage()
```

## Replace Record with Data Class

**When**: Using dict/tuple for structured data

```python
# Before - primitive obsession
concept = {
    "title": "Story Title",
    "logline": "Story premise",
    "genre": "SciFi",
}

# Typo-prone, no IDE support
print(concept["titel"])  # Runtime error!

# After - structured data class
@dataclass(frozen=True)
class Concept:
    title: str
    logline: str
    genre: str

concept = Concept(
    title="Story Title",
    logline="Story premise",
    genre="SciFi",
)

# Type-safe, IDE autocomplete
print(concept.title)  # ✅
print(concept.titel)  # ❌ Caught by IDE/pyright
```

## Preserve Whole Object

**When**: Passing multiple attributes instead of the object

```python
# Before - passing individual fields
def validate_concept_title(
    title: str,
    max_length: int,
    required: bool,
) -> None:
    if required and not title.strip():
        raise ValidationError("Title required")
    if len(title) > max_length:
        raise ValidationError("Title too long")

# Caller
validate_concept_title(
    concept.title,
    concept.max_title_length,
    concept.title_required,
)

# After - pass the whole object
def validate_concept_title(concept: Concept) -> None:
    if concept.title_required and not concept.title.strip():
        raise ValidationError("Title required")
    if len(concept.title) > concept.max_title_length:
        raise ValidationError("Title too long")

# Caller
validate_concept_title(concept)
```
