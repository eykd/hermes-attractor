---
name: architecture-review
description: "Use when: (1) Validating hexagonal architecture layer boundaries (domain/ports/adapters/use_cases/plugin), (2) Checking dependency direction rules, (3) Reviewing imports for layer violations, (4) Auditing that domain has zero dependencies and dependencies point inward."
---

# Architecture Review Skill

Validate hexagonal architecture boundaries and dependency rules for hermes_attractor.

## Hexagonal Architecture Rules

### Layer Dependencies (Strict)

```
domain/         → None (zero dependencies)
ports/          → domain only
adapters/       → domain, ports
use_cases/      → domain, ports
plugin/         → all layers (but minimal logic; isolates Hermes coupling)
```

**Violations are CRITICAL findings.**

## Detection Method

1. **Parse imports** in Python files
2. **Identify layer** from file path
3. **Check imports** against allowed dependencies
4. **Report violations** as Critical/High findings

## Layer Identification

```python
# Examples
src/hermes_attractor/domain/concept.py       → domain layer
src/hermes_attractor/ports/storage.py        → ports layer
src/hermes_attractor/adapters/file_storage.py → adapters layer
src/hermes_attractor/use_cases/create.py     → use_cases layer
src/hermes_attractor/plugin/hooks.py         → plugin layer
```

## Dependency Rules

### Domain (No Dependencies)

```python
# ❌ Violation - domain importing from ports
from hermes_attractor.ports.storage import StorageProtocol  # CRITICAL

# ❌ Violation - domain importing from adapters
from hermes_attractor.adapters.file import FileAdapter  # CRITICAL

# ✅ Allowed - domain importing domain
from hermes_attractor.domain.exceptions import ValidationError

# ✅ Allowed - standard library
from dataclasses import dataclass
from typing import Protocol
```

### Ports (Domain Only)

```python
# ❌ Violation - ports importing from adapters
from hermes_attractor.adapters.file import FileAdapter  # CRITICAL

# ❌ Violation - ports importing from use_cases
from hermes_attractor.use_cases.create import CreateUseCase  # HIGH

# ✅ Allowed - ports importing domain
from hermes_attractor.domain.concept import Concept

# ✅ Allowed - standard library
from abc import ABC, abstractmethod
```

### Adapters (Domain + Ports)

```python
# ❌ Violation - adapter importing from use_cases
from hermes_attractor.use_cases.create import CreateUseCase  # HIGH

# ❌ Violation - adapter importing from plugin
from hermes_attractor.plugin.hooks import create_hook  # HIGH

# ✅ Allowed - adapter importing domain
from hermes_attractor.domain.concept import Concept

# ✅ Allowed - adapter importing ports
from hermes_attractor.ports.storage import StorageProtocol

# ✅ Allowed - third-party libraries
import httpx
```

### Use Cases (Domain + Ports)

```python
# ❌ Violation - use case importing from adapters
from hermes_attractor.adapters.file import FileAdapter  # HIGH

# ❌ Violation - use case importing from plugin
from hermes_attractor.plugin.hooks import create_hook  # HIGH

# ✅ Allowed - use case importing domain
from hermes_attractor.domain.concept import Concept

# ✅ Allowed - use case importing ports
from hermes_attractor.ports.storage import StorageProtocol
```

### Plugin (All Layers - But Minimal Logic)

The `plugin/` layer isolates the Hermes Agent coupling (hooks, registration,
wiring). It is the only layer allowed to depend on Hermes APIs.

```python
# ✅ Allowed - plugin can import from all layers
from hermes_attractor.domain.concept import Concept
from hermes_attractor.ports.storage import StorageProtocol
from hermes_attractor.adapters.file import FileAdapter  # For wiring
from hermes_attractor.use_cases.create import CreateUseCase

# ❌ Bad practice - business logic in the plugin layer
def on_create_hook(title: str) -> None:
    if len(title) > 100:  # Validation belongs in domain!
        raise ValidationError("Title too long")
```

## Severity Levels

### Critical
- Domain importing from any other layer
- Circular dependencies between layers

### High
- Ports importing from adapters/use_cases/plugin
- Adapters importing from use_cases/plugin
- Use_cases importing from adapters/plugin
- Hermes APIs imported outside the `plugin/` layer

### Medium
- Business logic in plugin layer (should be in use_cases/domain)
- Direct adapter instantiation in use_cases (should use ports)

### Low
- Sub-optimal module organization within a layer

## Output Format

For each violation:

```bash
npx bd create "[architecture] Layer violation: [description]" \
  --description "File: [path]
Line: [line-number]
Severity: [Critical/High/Medium]
Skill: architecture-review

Problem:
[layer] importing from [illegal-layer]
Import: from [module] import [name]

This violates hexagonal architecture rules:
[layer] → [allowed dependencies only]

Fix:
1. Remove the illegal import
2. [specific guidance for fixing the dependency]
3. Run tests to ensure functionality preserved" \
  --priority [0-1] \
  --parent [epic-id]
```

## Common Fixes

### Domain importing from ports
**Fix**: Move interface to domain or make it a protocol

### Use case importing from adapter
**Fix**: Use port interface, inject adapter via dependency injection

### Business logic in plugin layer
**Fix**: Extract to use case, call use case from the plugin hook

## References

- CLAUDE.md (root) - Hexagonal architecture overview
- Layer-specific CLAUDE.md files - Dependency rules per layer
- /prefactoring skill - Architecture patterns reference
