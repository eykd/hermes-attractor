# Moving Refactorings

## Move Function Between Modules

**When**: Function is in wrong module (wrong responsibility)

```python
# Before - validation in storage module
# storage.py
class ConceptStorage:
    def save(self, concept: Concept) -> None:
        if not concept.title:  # Validation doesn't belong here!
            raise ValidationError("Title required")
        self._write_to_file(concept)

# After - validation in domain module
# domain/validation.py
def validate_concept(concept: Concept) -> None:
    if not concept.title:
        raise ValidationError("Title required")

# storage.py
class ConceptStorage:
    def save(self, concept: Concept) -> None:
        self._write_to_file(concept)  # Just storage logic
```

## Move Method Between Classes

**When**: Method uses another class more than its own

```python
# Before - method in wrong class
class Concept:
    def __init__(self, title: str, stage: Stage) -> None:
        self.title = title
        self.stage = stage

class ConceptFormatter:
    def format(self, concept: Concept) -> str:
        # Uses Stage more than Concept
        if concept.stage == Stage.CONCEPT:
            prefix = "[CONCEPT]"
        elif concept.stage == Stage.PREMISE:
            prefix = "[PREMISE]"
        else:
            prefix = "[OTHER]"
        return f"{prefix} {concept.title}"

# After - method moved to Stage
from enum import Enum

class Stage(Enum):
    CONCEPT = "concept"
    PREMISE = "premise"
    THEME = "theme"

    def format_prefix(self) -> str:
        """Get the display prefix for this stage."""
        prefixes = {
            Stage.CONCEPT: "[CONCEPT]",
            Stage.PREMISE: "[PREMISE]",
            Stage.THEME: "[THEME]",
        }
        return prefixes.get(self, "[OTHER]")

class ConceptFormatter:
    def format(self, concept: Concept) -> str:
        prefix = concept.stage.format_prefix()  # Delegate to Stage
        return f"{prefix} {concept.title}"
```

## Move to Correct Layer

**When**: Code is in wrong hexagonal layer

```python
# Before - domain logic in the plugin layer
# plugin/hooks.py
def on_create_concept(title: str) -> None:
    # Domain validation in the plugin layer! Wrong layer!
    if not title.strip():
        raise ValidationError("Title required")
    if len(title) > 100:
        raise ValidationError("Title too long")

    concept = Concept(title)
    storage.save(concept)

# After - validation in domain, the plugin hook is thin
# domain/validation.py
def validate_title(title: str) -> None:
    if not title.strip():
        raise ValidationError("Title required")
    if len(title) > 100:
        raise ValidationError("Title too long")

# plugin/hooks.py
def on_create_concept(title: str) -> str | None:
    try:
        validate_title(title)  # Use domain validation
        concept = Concept(title)
        storage.save(concept)
        return None
    except ValidationError as e:
        return f"Error: {e}"
```

## Extract Module

**When**: Module has grown too large

```python
# Before - everything in one module
# domain/concept.py (500 lines)
class Concept: ...
class ConceptValidator: ...
class ConceptFormatter: ...
class ConceptBuilder: ...
# ... 400 more lines

# After - split into focused modules
# domain/concept.py
class Concept: ...

# domain/concept_validation.py
class ConceptValidator: ...

# domain/concept_formatting.py
class ConceptFormatter: ...

# domain/concept_builder.py
class ConceptBuilder: ...
```
