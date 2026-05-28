---
name: pytest-hypothesis
description: "Use when: (1) Testing code with many possible inputs or edge cases, (2) Finding edge cases automatically (empty lists, Unicode, boundaries), (3) Creating custom strategies for domain objects, (4) Testing invariants across auto-generated inputs, (5) Model-based/stateful testing. Complements example-based tests."
---

# Property-Based Testing with Hypothesis

## Core Concept

Property-based testing verifies **invariants** (properties that should always hold) across auto-generated inputs, complementing example-based tests that check specific input-output pairs.

```python
# Example-based: Tests ONE specific case
def test_reverse_example():
    assert reverse("hello") == "olleh"

# Property-based: Tests the INVARIANT across thousands of cases
@given(st.text())
def test_reverse_property(s):
    assert reverse(reverse(s)) == s  # Roundtrip property
```

## When to Use Property-Based Testing

| Use Property-Based | Use Example-Based |
|-------------------|-------------------|
| Many valid inputs exist | Specific business rules |
| Edge cases hard to enumerate | Known corner cases |
| Testing invariants/properties | Testing exact outputs |
| Parsing, encoding, serialization | Specific user stories |

## Installation

```bash
uv add --group=test hypothesis
```

## Essential Imports

```python
from hypothesis import given, assume, settings, strategies as st
from hypothesis.strategies import composite
import pytest
```

## The @given Decorator

Transform any test into a property-based test:

```python
@given(st.integers(), st.integers())
def test_addition_commutative(a, b):
    assert a + b == b + a

@given(st.lists(st.integers(), min_size=1))
def test_max_in_list(lst):
    assert max(lst) in lst
```

Hypothesis runs the test ~100 times with different generated inputs and **shrinks** failures to minimal examples.

## Common Strategies Quick Reference

| Strategy | Generates | Key Parameters |
|----------|-----------|----------------|
| `st.integers()` | Ints | `min_value`, `max_value` |
| `st.floats()` | Floats | `allow_nan`, `allow_infinity`, `min_value`, `max_value` |
| `st.text()` | Unicode strings | `min_size`, `max_size`, `alphabet` |
| `st.binary()` | Bytes | `min_size`, `max_size` |
| `st.booleans()` | True/False | — |
| `st.none()` | None | — |
| `st.lists(strategy)` | Lists | `min_size`, `max_size`, `unique` |
| `st.dictionaries(keys, values)` | Dicts | `min_size`, `max_size` |
| `st.fixed_dictionaries({...})` | Dicts with specific keys | — |
| `st.sampled_from(seq)` | Element from sequence | — |
| `st.one_of(st1, st2)` | Either strategy | — |
| `st.builds(cls, ...)` | Class instances | — |

## Property Types to Test

### 1. Roundtrip/Symmetry
Encode then decode returns original:
```python
@given(st.binary())
def test_compress_roundtrip(data):
    assert decompress(compress(data)) == data
```

### 2. Invariants
Properties that always hold:
```python
@given(st.lists(st.integers()))
def test_sort_preserves_length(lst):
    assert len(sorted(lst)) == len(lst)

@given(st.lists(st.integers()))
def test_sort_preserves_elements(lst):
    assert sorted(sorted(lst)) == sorted(lst)  # Idempotent
```

### 3. Oracle Comparison
Compare against known-correct implementation:
```python
@given(st.lists(st.integers()))
def test_my_sort_matches_builtin(lst):
    assert my_sort(lst) == sorted(lst)
```

### 4. Commutativity/Associativity
```python
@given(st.integers(), st.integers())
def test_multiply_commutative(a, b):
    assert a * b == b * a
```

## Using assume() for Preconditions

Filter out invalid inputs (use sparingly—prefer constrained strategies):

```python
@given(st.integers(), st.integers())
def test_division(a, b):
    assume(b != 0)  # Skip when b is 0
    assert (a * b) / b == a
```

## Custom Strategies with @composite

Build complex domain objects:

```python
@st.composite
def user_strategy(draw):
    name = draw(st.text(min_size=1, max_size=50))
    age = draw(st.integers(min_value=0, max_value=150))
    email = draw(st.emails())
    return User(name=name, age=age, email=email)

@given(user_strategy())
def test_user_can_be_serialized(user):
    assert User.from_json(user.to_json()) == user
```

## Settings Configuration

```python
from hypothesis import settings, Phase

@settings(max_examples=500)  # More examples (default: 100)
@given(st.integers())
def test_with_more_examples(n): ...

@settings(deadline=None)  # Disable timing (slow tests)
@given(st.text())
def test_slow_operation(s): ...

@settings(suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.integers()))
def test_suppress_warning(lst): ...
```

## Edge Cases Hypothesis Finds

Hypothesis automatically tries these edge cases:
- Empty collections: `[]`, `""`, `{}`
- Boundary values: `0`, `-1`, `MAX_INT`
- Unicode edge cases: `"\x00"`, surrogate pairs
- NaN, infinity for floats
- Duplicate values in lists
- Very long strings/lists

## Combining with pytest Features

```python
# With fixtures
@pytest.fixture
def database():
    return MockDatabase()

@given(st.text())
def test_with_fixture(database, text):
    database.store(text)
    assert database.retrieve() == text

# With parametrize (runs each param with many generated values)
@pytest.mark.parametrize("operation", [str.upper, str.lower, str.strip])
@given(st.text())
def test_string_operations_reversible(operation, s):
    result = operation(s)
    assert isinstance(result, str)
```

## Common Patterns

### Testing Data Classes
```python
@st.composite
def order_strategy(draw):
    items = draw(st.lists(item_strategy(), min_size=1, max_size=10))
    return Order(items=items)

@given(order_strategy())
def test_order_total_positive(order):
    assert order.total() >= 0
```

### Testing APIs/Serialization
```python
@given(st.builds(MyModel, name=st.text(), value=st.integers()))
def test_model_serialization(model):
    json_str = model.to_json()
    restored = MyModel.from_json(json_str)
    assert restored == model
```

## Debugging Failed Tests

When a test fails, Hypothesis:
1. Prints the **failing example**
2. **Shrinks** to find minimal failing case
3. Stores in `.hypothesis/` database for replay

```
Falsifying example: test_my_function(x=[0, -1])
# Hypothesis found the simplest input that fails
```

## Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Over-constraining strategies | Misses edge cases | Start broad, constrain minimally |
| Excessive `assume()` | Slow, many discards | Use constrained strategies instead |
| Testing implementation | Fragile tests | Test observable behavior |
| Ignoring shrunk examples | Miss root cause | Analyze minimal failing input |

## Quick Decision Guide

**"What property should I test?"**
- Can I reverse the operation? → Roundtrip
- Does order/count matter? → Invariant
- Do I have a reference implementation? → Oracle
- Is it mathematically defined? → Mathematical property

**"My test is slow"**
- Add `@settings(deadline=None)`
- Reduce `max_examples`
- Constrain strategy sizes

**"Too many assume() calls"**
- Use `st.integers(min_value=1)` instead of `assume(n > 0)`
- Use `st.lists(..., min_size=1)` instead of `assume(len(lst) > 0)`
- Create custom strategy with `@composite`

## Detailed References

For comprehensive guidance:
- **[strategies.md](references/strategies.md)**: Complete strategy reference with all parameters and combinations
- **[patterns.md](references/patterns.md)**: Property patterns and real-world examples by domain
- **[stateful.md](references/stateful.md)**: Model-based stateful testing with RuleBasedStateMachine
