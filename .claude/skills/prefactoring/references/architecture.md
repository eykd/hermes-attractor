# Architecture Patterns

## Hexagonal Architecture (Ports and Adapters)

hermes_attractor follows strict hexagonal boundaries:

```
domain/         # Core business logic
  → No dependencies (pure Python)
  → Entities, value objects, domain services
  → Domain exceptions

ports/          # Interface definitions
  → Depends on: domain only
  → Protocols and ABCs
  → Repository and service interfaces

adapters/       # External integrations
  → Depends on: domain, ports
  → File I/O, API clients, config
  → Implement port interfaces

use_cases/      # Application orchestration
  → Depends on: domain, ports
  → Coordinate domain objects
  → Call ports for external access

plugin/         # Integration layer (Hermes coupling isolated here)
  → Depends on: all layers (thin logic)
  → Hermes hooks, registration, wiring
  → Delegate to use cases
```

## Module Responsibility

**One clear responsibility per module:**

```python
# Good
# domain/title.py - Title value object only
# domain/genre.py - Genre value object only

# Bad
# domain/models.py - Everything dumped in one file
```

## Dependency Direction

**Always point dependencies inward:**

```python
# ✅ Good - adapter depends on port
from hermes_attractor.ports.storage import StorageProtocol
class FileStorageAdapter(StorageProtocol): ...

# ❌ Bad - port depends on adapter
from hermes_attractor.adapters.file_storage import FileStorageAdapter
class StorageProtocol(Protocol): ...
```

## Choosing the Right Layer

| What are you building? | Layer | Why? |
|------------------------|-------|------|
| Business rule/validation | domain | Pure logic, no I/O |
| Interface contract | ports | Define "what", not "how" |
| File/DB/API integration | adapters | Implement port contracts |
| User story orchestration | use_cases | Coordinate domain + ports |
| Hermes hook handling | plugin | Bridge Hermes events to use cases |

## References

- CLAUDE.md (root) - Hexagonal architecture overview
- src/hermes_attractor/domain/CLAUDE.md - Domain layer patterns
- src/hermes_attractor/ports/CLAUDE.md - Port interface patterns
