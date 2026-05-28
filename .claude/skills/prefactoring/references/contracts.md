# Contracts (Interfaces)

## Protocols vs ABCs

**Use Protocol for structural typing (duck typing):**

```python
from typing import Protocol

class StorageProtocol(Protocol):
    """Anything that can save/load artifacts."""

    def save(self, artifact: Artifact) -> None: ...
    def load(self, artifact_id: str) -> Artifact: ...

# No inheritance needed, just implement methods
class FileStorage:
    def save(self, artifact: Artifact) -> None: ...
    def load(self, artifact_id: str) -> Artifact: ...

# Type checker validates structure
storage: StorageProtocol = FileStorage()  # ✅ Works
```

**Use ABC for explicit contracts (nominal typing):**

```python
from abc import ABC, abstractmethod

class ArtifactRepository(ABC):
    """Base class for artifact repositories."""

    @abstractmethod
    def save(self, artifact: Artifact) -> None:
        """Save artifact to storage."""

    @abstractmethod
    def load(self, artifact_id: str) -> Artifact:
        """Load artifact from storage."""

# Must explicitly inherit
class FileRepository(ArtifactRepository):  # Explicit contract
    def save(self, artifact: Artifact) -> None: ...
    def load(self, artifact_id: str) -> Artifact: ...
```

## When to Use Which

| Use Protocol | Use ABC |
|--------------|---------|
| Third-party code you don't control | You own all implementations |
| Flexible, structural matching | Explicit inheritance required |
| Testing with simple test doubles | Shared behavior in base class |
| Simpler, more Pythonic | More explicit, Java-like |

## Design Interfaces Before Implementations

**Start with the contract:**

```python
# 1. Define what you need (port)
class ConceptStorageProtocol(Protocol):
    def save_concept(self, concept: Concept) -> None: ...
    def load_concept(self, concept_id: str) -> Concept: ...

# 2. Use in use case (depend on interface)
class CreateConceptUseCase:
    def __init__(self, storage: ConceptStorageProtocol) -> None:
        self.storage = storage

# 3. Implement later (adapter)
class FileConceptStorage:
    def save_concept(self, concept: Concept) -> None:
        # Implementation details
        ...
```

## Interface Segregation

**Many small interfaces > one large interface:**

```python
# ✅ Good - focused interfaces
class ConceptReader(Protocol):
    def load_concept(self, id: str) -> Concept: ...

class ConceptWriter(Protocol):
    def save_concept(self, concept: Concept) -> None: ...

# Use case only needs reading
class ListConceptsUseCase:
    def __init__(self, reader: ConceptReader) -> None: ...

# ❌ Bad - forced to depend on unused methods
class ConceptStorage(Protocol):
    def load_concept(self, id: str) -> Concept: ...
    def save_concept(self, concept: Concept) -> None: ...
    def delete_concept(self, id: str) -> None: ...
    def update_concept(self, concept: Concept) -> None: ...
```

## Liskov Substitution

**Subtypes must be substitutable for their base types:**

```python
# ✅ Good - same contract
class StorageProtocol(Protocol):
    def save(self, artifact: Artifact) -> None: ...

class FileStorage:  # Can substitute
    def save(self, artifact: Artifact) -> None: ...

class S3Storage:  # Can substitute
    def save(self, artifact: Artifact) -> None: ...

# ❌ Bad - broken contract
class BrokenStorage:
    def save(self, artifact: Artifact) -> str:  # Changed return type!
        ...
```

## References

- PEP 544: https://peps.python.org/pep-0544/
- SOLID principles (Interface Segregation, Liskov Substitution)
