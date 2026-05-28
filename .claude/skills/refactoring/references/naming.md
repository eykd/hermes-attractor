# Naming Refactorings

## Rename Variable

**When**: Variable name doesn't reveal intent

```python
# Before
def process(c: Concept) -> None:
    t = c.title
    d = datetime.now()
    x = calculate(t, d)  # What is x?

# After
def process(concept: Concept) -> None:
    title = concept.title
    current_date = datetime.now()
    validation_score = calculate(title, current_date)
```

## Rename Function

**When**: Function name is misleading or vague

```python
# Before
def proc(concept: Concept) -> None:  # Process? Procedure?
    validate_concept_fields(concept)

# After
def validate_concept(concept: Concept) -> None:
    validate_concept_fields(concept)
```

## Rename Class

**When**: Class name doesn't match responsibility

```python
# Before
class Manager:  # Manager of what?
    def create_concept(self) -> Concept: ...
    def validate_concept(self, concept: Concept) -> None: ...

# After
class ConceptService:  # Clear responsibility
    def create_concept(self) -> Concept: ...
    def validate_concept(self, concept: Concept) -> None: ...
```

## Rename Module

**When**: Module name is too generic or misleading

```python
# Before
# utils.py - what utilities?
class ConceptValidator: ...
class ConceptStorage: ...

# After - split into focused modules
# concept_validation.py
class ConceptValidator: ...

# concept_storage.py
class ConceptStorage: ...
```

## Change Function Signature

**When**: Parameters are unclear or in wrong order

```python
# Before - positional args confusing
def create_concept(
    title: str,
    logline: str,
    genre: str,
    author: str,
    created: datetime,
    modified: datetime,
) -> Concept:
    ...

# Caller
create_concept("Title", "Logline", "Author", "SciFi", now, now)  # Wrong order!

# After - explicit parameter object
@dataclass(frozen=True)
class ConceptParams:
    title: str
    logline: str
    genre: str
    author: str
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)

def create_concept(params: ConceptParams) -> Concept:
    ...

# Caller - clear and safe
create_concept(ConceptParams(
    title="Title",
    logline="Logline",
    genre="SciFi",
    author="Author",
))
```

## Replace Magic Number with Named Constant

```python
# Before
def validate_title(title: str) -> None:
    if len(title) > 100:  # Why 100?
        raise ValidationError("Title too long")

# After
MAX_TITLE_LENGTH = 100

def validate_title(title: str) -> None:
    if len(title) > MAX_TITLE_LENGTH:
        raise ValidationError("Title too long")
```
