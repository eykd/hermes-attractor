---
name: error-handling-patterns
description: "Use when: (1) Designing domain exception hierarchies, (2) Deciding between exceptions and Result types, (3) Implementing validation logic, (4) Handling external service failures, (5) Structuring safe, user-facing error responses for the CLI."
---

# Error Handling Patterns Skill

Design robust error handling using exception hierarchies, Result types, and safe error responses.

## When to Use

**During design phase:**
- Creating domain exceptions
- Deciding exception vs Result type
- Structuring error responses for CLI

**During implementation:**
- Implementing validation logic
- Handling external service failures
- Ensuring safe error messages

## Decision Tree

```
Handling an error scenario?
├─ Domain-specific error?
│  └─→ See: references/exception-hierarchy.md
├─ Expected failure (parse, validation)?
│  └─→ See: references/result-types.md
└─ Need user-facing error message?
   └─→ See: references/safe-errors.md
```

## Quick Principles

### 1. Exception Hierarchy (references/exception-hierarchy.md)
- Base exception: `HermesAttractorError`
- Domain exceptions: `ValidationError`, `StageError`, etc.
- Never catch `Exception` (too broad)

### 2. Result Types (references/result-types.md)
- Use for expected failures (parsing, validation)
- Use exceptions for unexpected failures (I/O errors, bugs)
- Pattern matching for Result handling

### 3. Safe Errors (references/safe-errors.md)
- No sensitive data in error messages
- No implementation details exposed
- User-friendly language for CLI

## Exception vs Result

**Use Exception when:**
- Failure is unexpected (bug, system error)
- Caller should not ignore (crashes are acceptable)
- Call stack unwinding is appropriate

**Use Result when:**
- Failure is expected and part of normal flow
- Caller needs to handle both success and failure
- Railway-oriented programming desired

## Example

```python
# Exception (unexpected)
def load_from_disk(path: Path) -> Concept:
    if not path.exists():
        raise StorageError(f"File not found")  # Unexpected!
    ...

# Result (expected)
def parse_concept(data: str) -> Result[Concept]:
    try:
        concept = json.loads(data)
        return Success(Concept(**concept))
    except (json.JSONDecodeError, KeyError) as e:
        return Failure("Invalid concept data")  # Expected possibility
```

## References

Detailed patterns in `references/` directory:
- exception-hierarchy.md - Domain exception design
- result-types.md - Result/Either pattern in Python
- safe-errors.md - Error messages without disclosure
