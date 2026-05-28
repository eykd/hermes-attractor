# Separation of Concerns

## DRY (Don't Repeat Yourself)

**Extract duplicated logic:**

```python
# ❌ Bad - duplication
def validate_concept(concept: Concept) -> None:
    if not concept.title.strip():
        raise ValidationError("Title required")
    if not concept.logline.strip():
        raise ValidationError("Logline required")

def validate_premise(premise: Premise) -> None:
    if not premise.title.strip():
        raise ValidationError("Title required")
    if not premise.conflict.strip():
        raise ValidationError("Conflict required")

# ✅ Good - extracted common validation
def validate_required_field(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValidationError(f"{field_name} required")

def validate_concept(concept: Concept) -> None:
    validate_required_field(concept.title, "Title")
    validate_required_field(concept.logline, "Logline")
```

## Policy vs Implementation

**Separate "what" from "how":**

```python
# ❌ Bad - policy mixed with implementation
def process_concept(concept: Concept) -> None:
    # Policy: Validate then save
    if not concept.title:
        raise ValidationError("Invalid")
    with open("concept.json", "w") as f:  # Implementation detail
        json.dump(concept.dict(), f)

# ✅ Good - policy separate from implementation
def process_concept(
    concept: Concept,
    storage: StorageProtocol
) -> None:
    validate_concept(concept)  # What (policy)
    storage.save(concept)      # How (implementation via port)
```

## Single Level of Abstraction

**Each function operates at one level:**

```python
# ❌ Bad - mixed abstraction levels
def create_story() -> None:
    concept = Concept(...)  # High-level
    if not concept.title.strip():  # Low-level detail
        raise ValidationError("Title required")
    storage.save(concept)  # High-level

# ✅ Good - consistent abstraction level
def create_story() -> None:
    concept = create_concept()
    validate_concept(concept)
    save_concept(concept)
```

## Cohesion

**Related things together, unrelated things apart:**

```python
# ✅ Good - cohesive module
# domain/title.py
class Title:
    ...
def validate_title(title: Title) -> None:
    ...

# ❌ Bad - low cohesion
# domain/utilities.py
class Title: ...
class Logger: ...
def format_date(): ...
```

## Function Length

**Keep functions short and focused:**

```python
# ✅ Good - one clear responsibility
def validate_concept_title(title: str) -> None:
    if not title.strip():
        raise ValidationError("Title cannot be empty")
    if len(title) > 100:
        raise ValidationError("Title too long")

# ❌ Bad - doing too much
def process_everything(data: dict) -> None:
    # 50 lines of validation
    # 30 lines of transformation
    # 40 lines of persistence
    # 20 lines of notification
```

## References

- Clean Code (Martin) - Chapter 3: Functions
- Refactoring (Fowler) - Extract Function
