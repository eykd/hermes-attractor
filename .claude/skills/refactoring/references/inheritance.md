# Inheritance Refactorings

## Replace Inheritance with Composition

**When**: Inheritance is used for code reuse, not "is-a" relationship

```python
# Before - inheritance for reuse (bad)
class FileHandler:
    def read_file(self, path: Path) -> str:
        with open(path) as f:
            return f.read()

    def write_file(self, path: Path, content: str) -> None:
        with open(path, "w") as f:
            f.write(content)

class ConceptStorage(FileHandler):  # Not "is-a" relationship!
    def save(self, concept: Concept) -> None:
        content = json.dumps(concept.dict())
        self.write_file(Path("concept.json"), content)

# After - composition
class FileHandler:
    def read_file(self, path: Path) -> str:
        with open(path) as f:
            return f.read()

    def write_file(self, path: Path, content: str) -> None:
        with open(path, "w") as f:
            f.write(content)

class ConceptStorage:
    def __init__(self, file_handler: FileHandler) -> None:
        self._file_handler = file_handler  # Composition

    def save(self, concept: Concept) -> None:
        content = json.dumps(concept.dict())
        self._file_handler.write_file(Path("concept.json"), content)
```

## Replace Inheritance with Protocol

**When**: Only need structural typing, not implementation inheritance

```python
# Before - inheritance for interface
from abc import ABC, abstractmethod

class Validator(ABC):
    @abstractmethod
    def validate(self, value: str) -> bool:
        pass

class TitleValidator(Validator):
    def validate(self, value: str) -> bool:
        return len(value) > 0

# After - protocol (more Pythonic)
from typing import Protocol

class Validator(Protocol):
    def validate(self, value: str) -> bool: ...

class TitleValidator:  # No inheritance needed
    def validate(self, value: str) -> bool:
        return len(value) > 0
```

## Pull Up Common Behavior

**When**: Multiple subclasses have same code

```python
# Before - duplication in subclasses
class ConceptValidator:
    def validate(self, concept: Concept) -> None:
        self._log_validation("concept")  # Duplicate
        if not concept.title:
            raise ValidationError("Title required")

    def _log_validation(self, type_: str) -> None:
        print(f"Validating {type_}")

class PremiseValidator:
    def validate(self, premise: Premise) -> None:
        self._log_validation("premise")  # Duplicate
        if not premise.conflict:
            raise ValidationError("Conflict required")

    def _log_validation(self, type_: str) -> None:  # Duplicate!
        print(f"Validating {type_}")

# After - pull up to base class
class BaseValidator:
    def _log_validation(self, type_: str) -> None:
        print(f"Validating {type_}")

class ConceptValidator(BaseValidator):
    def validate(self, concept: Concept) -> None:
        self._log_validation("concept")
        if not concept.title:
            raise ValidationError("Title required")

class PremiseValidator(BaseValidator):
    def validate(self, premise: Premise) -> None:
        self._log_validation("premise")
        if not premise.conflict:
            raise ValidationError("Conflict required")
```

## Replace Type Code with Subclasses

**When**: Behavior differs based on type code

```python
# Before - type code
class Artifact:
    def __init__(self, type_: str, content: str) -> None:
        self.type_ = type_
        self.content = content

    def validate(self) -> None:
        if self.type_ == "concept":
            # Concept-specific validation
            pass
        elif self.type_ == "premise":
            # Premise-specific validation
            pass

# After - subclasses
class Artifact:
    def __init__(self, content: str) -> None:
        self.content = content

    def validate(self) -> None:
        raise NotImplementedError

class Concept(Artifact):
    def validate(self) -> None:
        # Concept-specific validation
        pass

class Premise(Artifact):
    def validate(self) -> None:
        # Premise-specific validation
        pass
```

## Collapse Hierarchy

**When**: Subclass doesn't add enough value

```python
# Before - unnecessary hierarchy
class Validator:
    def validate(self, value: str) -> bool:
        raise NotImplementedError

class ConceptValidator(Validator):
    def validate(self, value: str) -> bool:  # Only implementation
        return len(value) > 0

# After - single class
class ConceptValidator:
    def validate(self, value: str) -> bool:
        return len(value) > 0
```

## Favor Composition Over Inheritance

**Python maxim: Use composition unless you have a clear "is-a" relationship**

```python
# ❌ Bad - inheritance for code reuse
class LoggerMixin:
    def log(self, msg: str) -> None:
        print(msg)

class ConceptService(LoggerMixin):  # ConceptService "is-a" Logger?
    def create(self) -> None:
        self.log("Creating concept")

# ✅ Good - composition
class Logger:
    def log(self, msg: str) -> None:
        print(msg)

class ConceptService:
    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def create(self) -> None:
        self._logger.log("Creating concept")
```
