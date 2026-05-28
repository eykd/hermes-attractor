# Naming Conventions

## Reveal Intent

**Names should answer: What does this do? Why does it exist?**

```python
# ❌ Bad - vague, requires comments
def proc(d):  # Process data
    ...

# ✅ Good - intent clear from name
def validate_concept_fields(concept: Concept) -> None:
    ...
```

## Use Domain Language

**Speak the language of story development:**

```python
# ✅ Good - domain terms
class Premise: ...
class Beats: ...
class Scene: ...

# ❌ Bad - technical jargon
class Step2: ...
class ListNode: ...
class DataContainer: ...
```

## Avoid Abbreviations

**Use full words unless universally known:**

```python
# ✅ Good
calculate_total_price()
user_repository
http_client  # HTTP is universal

# ❌ Bad
calc_tot_pr()
usr_repo
hypertext_transfer_protocol_client  # Too verbose
```

## PEP 8 Style

```python
# Modules: snake_case
# file_storage.py

# Classes: PascalCase
class ConceptValidator: ...

# Functions/Variables: snake_case
def validate_concept(): ...
total_count = 0

# Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3

# Private: _leading_underscore
def _internal_helper(): ...
```

## Function Names

**Use verb phrases:**

```python
# Good
create_concept()
validate_structure()
calculate_next_stage()

# Bad (nouns)
concept()
validator()
stage()
```

## Boolean Names

**Use is/has/can prefixes:**

```python
# Good
is_valid: bool
has_errors: bool
can_proceed: bool

# Bad
valid: bool  # Verb or adjective?
errors: bool  # Sounds like a collection
proceed: bool  # Sounds like a function
```

## Type Variables

**Use descriptive names or single uppercase letters:**

```python
from typing import TypeVar

# Good
T = TypeVar("T")
ArtifactT = TypeVar("ArtifactT", bound=Artifact)

# Bad
type1 = TypeVar("type1")
x = TypeVar("x")
```

## References

- PEP 8: https://pep8.org
- Clean Code (Martin) - Chapter 2: Meaningful Names
