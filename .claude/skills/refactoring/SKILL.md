---
name: refactoring
description: "Use during TDD's REFACTOR phase, after tests are GREEN: (1) removing duplication, (2) renaming unclear names, (3) extracting functions, (4) improving encapsulation or moving methods, (5) simplifying complex code, (6) cleaning up before adding new features."
---

# Refactoring Skill

Improve code design AFTER tests pass. Following TDD's RED-GREEN-REFACTOR cycle, this skill applies during the REFACTOR phase.

## When to Use

**After tests are GREEN:**
- Code works but has code smells
- Duplication detected
- Names unclear or misleading
- Functions too long or complex
- Inappropriate coupling

**Before adding new features:**
- Clean up existing code first
- Make room for new functionality

## Decision Tree

```
Code smell detected?
├─ Duplicated code?
│  └─→ See: references/extraction.md (Extract Function/Method)
├─ Unclear names?
│  └─→ See: references/naming.md (Rename Variable/Function/Class)
├─ Data exposure/missing encapsulation?
│  └─→ See: references/encapsulation.md (Encapsulate Field)
├─ Method in wrong class?
│  └─→ See: references/moving.md (Move Method/Function)
├─ Mutable data causing issues?
│  └─→ See: references/data.md (Replace with immutable)
├─ Too many parameters?
│  └─→ See: references/api.md (Introduce Parameter Object)
├─ Dead code or unnecessary complexity?
│  └─→ See: references/simplification.md (Remove Dead Code)
└─ Inheritance problems?
   └─→ See: references/inheritance.md (Replace with Composition)
```

## Python-Specific Code Smells

### 1. Mutable Default Arguments
```python
# ❌ Smell
def add_item(item, items=[]):  # Shared across calls!
    items.append(item)
    return items

# ✅ Refactored
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

### 2. Bare Except Clauses
```python
# ❌ Smell
try:
    process_artifact()
except:  # Catches SystemExit, KeyboardInterrupt!
    handle_error()

# ✅ Refactored
try:
    process_artifact()
except HermesAttractorError as e:  # Specific exception
    handle_error(e)
```

### 3. Missing Type Hints
```python
# ❌ Smell
def calculate(x, y):  # What types?
    return x + y

# ✅ Refactored
def calculate(x: int, y: int) -> int:
    return x + y
```

### 4. Complex Comprehensions
```python
# ❌ Smell
result = [
    process(item.value.upper())
    for item in items
    if item.valid and item.value and len(item.value) > 5
]

# ✅ Refactored
def is_valid_item(item: Item) -> bool:
    return item.valid and item.value and len(item.value) > 5

result = [
    process(item.value.upper())
    for item in items
    if is_valid_item(item)
]
```

## Refactoring Safety

**Prerequisites:**
1. Tests exist and pass (100% coverage)
2. Version control (git) with clean working directory
3. Run tests after each refactoring step

**Process:**
1. Identify smell
2. Apply refactoring (one at a time)
3. Run tests (`uv run pytest`)
4. Commit if tests pass
5. Repeat

## References

Detailed refactoring patterns in `references/` directory:
- extraction.md - Extract function/method/class
- naming.md - Rename refactorings
- encapsulation.md - Hide data, expose behavior
- moving.md - Move method/function between modules
- data.md - Immutability, dataclasses
- api.md - Function signature improvements
- simplification.md - Remove dead code, inline
- inheritance.md - Composition over inheritance
