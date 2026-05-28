# Extraction Refactorings

## Extract Function

**When**: Code fragment can be grouped together

```python
# Before
def process_concept(concept: Concept) -> None:
    # Validate title
    if not concept.title.strip():
        raise ValidationError("Title required")
    if len(concept.title) > 100:
        raise ValidationError("Title too long")

    # Validate logline
    if not concept.logline.strip():
        raise ValidationError("Logline required")
    if len(concept.logline) > 500:
        raise ValidationError("Logline too long")

# After - extracted validation
def validate_title(title: str) -> None:
    if not title.strip():
        raise ValidationError("Title required")
    if len(title) > 100:
        raise ValidationError("Title too long")

def validate_logline(logline: str) -> None:
    if not logline.strip():
        raise ValidationError("Logline required")
    if len(logline) > 500:
        raise ValidationError("Logline too long")

def process_concept(concept: Concept) -> None:
    validate_title(concept.title)
    validate_logline(concept.logline)
```

## Extract Method

**When**: Method is too long or does multiple things

```python
# Before
class ConceptValidator:
    def validate(self, concept: Concept) -> None:
        # 50 lines of validation logic
        if not concept.title.strip():
            ...
        if not concept.logline.strip():
            ...
        if concept.genre not in VALID_GENRES:
            ...

# After
class ConceptValidator:
    def validate(self, concept: Concept) -> None:
        self._validate_title(concept.title)
        self._validate_logline(concept.logline)
        self._validate_genre(concept.genre)

    def _validate_title(self, title: str) -> None:
        if not title.strip():
            raise ValidationError("Title required")

    def _validate_logline(self, logline: str) -> None:
        if not logline.strip():
            raise ValidationError("Logline required")

    def _validate_genre(self, genre: str) -> None:
        if genre not in VALID_GENRES:
            raise ValidationError(f"Invalid genre: {genre}")
```

## Extract Class

**When**: Class has multiple responsibilities

```python
# Before - ConceptProcessor does too much
class ConceptProcessor:
    def validate(self, concept: Concept) -> None: ...
    def save_to_file(self, concept: Concept) -> None: ...
    def send_notification(self, concept: Concept) -> None: ...

# After - separated concerns
class ConceptValidator:
    def validate(self, concept: Concept) -> None: ...

class ConceptStorage:
    def save(self, concept: Concept) -> None: ...

class ConceptNotifier:
    def notify(self, concept: Concept) -> None: ...
```

## Extract Variable

**When**: Complex expression needs clarification

```python
# Before
if (
    concept.stage == Stage.CONCEPT
    and concept.is_valid
    and len(concept.title) > 0
    and concept.created_at < datetime.now() - timedelta(days=30)
):
    archive_concept(concept)

# After
is_old_concept = concept.created_at < datetime.now() - timedelta(days=30)
is_complete = concept.stage == Stage.CONCEPT and concept.is_valid
has_title = len(concept.title) > 0
should_archive = is_complete and has_title and is_old_concept

if should_archive:
    archive_concept(concept)
```

## Inline Function (Reverse)

**When**: Function body is as clear as its name

```python
# Before - unnecessary indirection
def get_title(concept: Concept) -> str:
    return concept.title

def process(concept: Concept) -> None:
    title = get_title(concept)  # Just use concept.title directly
    ...

# After - inlined
def process(concept: Concept) -> None:
    title = concept.title
    ...
```
