# Simplification Refactorings

## Remove Dead Code

**When**: Code is never used

```python
# Before - unused code
class Concept:
    def __init__(self, title: str) -> None:
        self.title = title

    def old_validate(self) -> bool:  # Never called!
        return len(self.title) > 0

    def validate(self) -> None:
        if not self.title.strip():
            raise ValidationError("Title required")

# After - deleted unused method
class Concept:
    def __init__(self, title: str) -> None:
        self.title = title

    def validate(self) -> None:
        if not self.title.strip():
            raise ValidationError("Title required")
```

## Inline Unnecessary Function

**When**: Function adds no value

```python
# Before - unnecessary wrapper
def get_title(concept: Concept) -> str:
    return concept.title

def process(concept: Concept) -> None:
    title = get_title(concept)  # Just use concept.title!
    print(title)

# After - inlined
def process(concept: Concept) -> None:
    print(concept.title)
```

## Replace Nested Conditional with Guard Clauses

**When**: Deep nesting obscures main logic

```python
# Before - nested conditions
def process_concept(concept: Concept) -> None:
    if concept is not None:
        if concept.is_valid:
            if concept.stage == Stage.CONCEPT:
                # Actual work buried deep
                do_processing(concept)

# After - guard clauses
def process_concept(concept: Concept | None) -> None:
    if concept is None:
        return
    if not concept.is_valid:
        return
    if concept.stage != Stage.CONCEPT:
        return

    # Main logic at top level
    do_processing(concept)
```

## Consolidate Duplicate Conditional Fragments

**When**: Same code in all branches

```python
# Before - duplication
def process_concept(concept: Concept, save: bool) -> None:
    if save:
        validate_concept(concept)
        storage.save(concept)
        log_action("saved")  # Duplicate
    else:
        validate_concept(concept)
        log_action("validated")  # Duplicate

# After - consolidate
def process_concept(concept: Concept, save: bool) -> None:
    validate_concept(concept)
    if save:
        storage.save(concept)
        log_action("saved")
    else:
        log_action("validated")
```

## Replace Complex Condition with Function

**When**: Condition is hard to understand

```python
# Before - complex condition
def can_advance(concept: Concept) -> bool:
    if (
        concept.stage == Stage.CONCEPT
        and concept.is_valid
        and len(concept.title) > 0
        and concept.created_at < datetime.now() - timedelta(days=30)
    ):
        return True
    return False

# After - named function for clarity
def is_mature_concept(concept: Concept) -> bool:
    """Check if concept is old enough to advance."""
    age = datetime.now() - concept.created_at
    return age > timedelta(days=30)

def can_advance(concept: Concept) -> bool:
    return (
        concept.stage == Stage.CONCEPT
        and concept.is_valid
        and len(concept.title) > 0
        and is_mature_concept(concept)
    )
```

## Replace Loop with Comprehension

**When**: Simple loop can be a comprehension

```python
# Before - loop
valid_concepts = []
for concept in concepts:
    if concept.is_valid:
        valid_concepts.append(concept)

# After - comprehension
valid_concepts = [c for c in concepts if c.is_valid]

# Before - complex loop
titles = []
for concept in concepts:
    if concept.is_valid:
        titles.append(concept.title.upper())

# After - comprehension
titles = [c.title.upper() for c in concepts if c.is_valid]
```

## Remove Assignments to Parameters

**When**: Function modifies its parameters

```python
# Before - modifying parameter (confusing!)
def discount(price: float, rate: float) -> float:
    price = price * (1 - rate)  # Modifies parameter!
    return price

# After - new variable
def discount(price: float, rate: float) -> float:
    discounted_price = price * (1 - rate)
    return discounted_price
```

## Decompose Complex Expression

**When**: Expression is hard to read

```python
# Before - complex expression
result = (
    concepts[0].title if concepts and concepts[0].is_valid else "Untitled"
) + " - " + (
    concepts[0].genre if concepts and concepts[0].genre else "Unknown"
)

# After - decomposed
def get_concept_title(concepts: list[Concept]) -> str:
    if concepts and concepts[0].is_valid:
        return concepts[0].title
    return "Untitled"

def get_concept_genre(concepts: list[Concept]) -> str:
    if concepts and concepts[0].genre:
        return concepts[0].genre
    return "Unknown"

title = get_concept_title(concepts)
genre = get_concept_genre(concepts)
result = f"{title} - {genre}"
```
