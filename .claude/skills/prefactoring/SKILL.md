---
name: prefactoring
description: "Use BEFORE writing new code (Ken Pugh's prefactoring): (1) designing modules/classes, (2) creating domain entities or value objects, (3) defining contracts (protocols/ABCs), (4) naming anything, (5) structuring control flow or error handling to avoid costly later refactoring."
---

# Prefactoring Skill

Apply Ken Pugh's prefactoring principles: **think before you code**. Make design decisions up front to avoid costly refactoring later.

## When to Use

**ALWAYS use before writing new code:**
- Designing new modules or classes
- Creating domain entities or value objects
- Defining contracts (protocols/ABCs)
- Naming anything (variables, functions, classes, modules)
- Structuring control flow or error handling

## Decision Tree

```
New code to write?
├─ Designing module/class structure?
│  └─→ See: references/architecture.md
├─ Creating domain types?
│  └─→ See: references/value-objects.md
├─ Naming something?
│  └─→ See: references/naming.md
├─ Organizing code/avoiding duplication?
│  └─→ See: references/separation.md
├─ Defining an interface/contract?
│  └─→ See: references/contracts.md
└─ Handling errors or validation?
   └─→ See: references/error-handling.md
```

## Quick Principles

### 1. Architecture (references/architecture.md)
- Hexagonal layers: domain → ports → adapters → use_cases → plugin
- One responsibility per module/class
- Dependencies point inward (domain has none)

### 2. Value Objects (references/value-objects.md)
- Wrap primitives in domain types (Title, not str)
- Use dataclasses/Pydantic for immutability
- Validate in `__post_init__` or Pydantic validators

### 3. Naming (references/naming.md)
- Reveal intent: `calculate_total_price` not `calc`
- Use domain language: `Premise` not `Step2`
- Avoid abbreviations unless ubiquitous (HTTP, ID)

### 4. Separation (references/separation.md)
- DRY: Extract common logic to functions/classes
- Separate policy (what) from implementation (how)
- Single Level of Abstraction per function

### 5. Contracts (references/contracts.md)
- Use protocols for structural typing
- Use ABCs for explicit contracts
- Design interfaces before implementations

### 6. Error Handling (references/error-handling.md)
- Domain exceptions inherit from base (HermesAttractorError)
- Validate at boundaries (user input, external APIs)
- Use Result types for expected failures

## Output Format

After prefactoring analysis, provide:

1. **Design Decision**: What pattern/approach to use
2. **Rationale**: Why this choice (cite principle)
3. **Structure**: Outline of classes/functions/modules
4. **Dependencies**: What imports/layers needed

## Example

```
Design Decision: Create Title value object instead of using str

Rationale:
- Wrap primitive (value-objects.md)
- Domain validation in one place
- Type safety prevents string confusion

Structure:
@dataclass(frozen=True)
class Title:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValidationError("Title cannot be empty")

Dependencies:
- hermes_attractor.domain.exceptions.ValidationError (domain → domain)
```

## References

Detailed guidance in `references/` directory:
- architecture.md - Module design, hexagonal boundaries
- value-objects.md - Wrapping primitives, Pydantic patterns
- naming.md - PEP 8, domain language, intent-revealing names
- separation.md - DRY, policy/implementation split, abstraction levels
- contracts.md - Protocols vs ABCs, interface design
- error-handling.md - Exception hierarchies, Result types
