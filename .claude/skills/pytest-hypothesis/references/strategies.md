# Hypothesis Strategies Reference

Complete reference for Hypothesis strategies with parameters and examples.

## Primitive Strategies

### Integers
```python
st.integers()                              # Any integer
st.integers(min_value=0)                   # Non-negative
st.integers(min_value=1, max_value=100)    # Range [1, 100]
```

### Floats
```python
st.floats()                                           # Any float (includes NaN, inf)
st.floats(allow_nan=False, allow_infinity=False)      # Finite only
st.floats(min_value=0.0, max_value=1.0)              # Range [0, 1]
st.floats(min_value=0.01, max_value=100.0,           # Positive, finite
          allow_nan=False, allow_infinity=False)
```

### Strings
```python
st.text()                                  # Unicode strings
st.text(min_size=1)                        # Non-empty
st.text(min_size=1, max_size=100)          # Length bounds
st.text(alphabet=st.characters(whitelist_categories=('L',)))  # Letters only
st.text(alphabet='abc123')                 # Custom alphabet

st.from_regex(r'[a-z]+@[a-z]+\.[a-z]{2,}')  # From regex pattern
```

### Binary
```python
st.binary()                                # Bytes
st.binary(min_size=1, max_size=1024)       # Size bounds
```

### Booleans and None
```python
st.booleans()                              # True or False
st.none()                                  # Always None
st.integers() | st.none()                  # Optional integer
```

## Collection Strategies

### Lists
```python
st.lists(st.integers())                              # List of ints
st.lists(st.integers(), min_size=1)                  # Non-empty
st.lists(st.integers(), min_size=1, max_size=10)     # Bounded size
st.lists(st.integers(), unique=True)                 # No duplicates
st.lists(st.integers(), unique_by=abs)               # Unique by function
```

### Sets and Frozensets
```python
st.sets(st.integers())                     # Set of ints
st.sets(st.integers(), min_size=1, max_size=10)
st.frozensets(st.integers())
```

### Dictionaries
```python
st.dictionaries(st.text(), st.integers())            # {str: int}
st.dictionaries(st.text(min_size=1), st.integers(),  # Bounded
                min_size=1, max_size=5)

# Fixed structure (specific keys)
st.fixed_dictionaries({
    'name': st.text(min_size=1),
    'age': st.integers(min_value=0, max_value=150),
    'active': st.booleans()
})

# Optional keys
st.fixed_dictionaries(
    {'required': st.integers()},
    optional={'maybe': st.text()}
)
```

### Tuples
```python
st.tuples(st.integers(), st.text())        # (int, str)
st.tuples(st.integers(), st.integers(), st.integers())  # 3-tuple
```

## Selection Strategies

### From Sequence
```python
st.sampled_from(['red', 'green', 'blue'])  # Choose from list
st.sampled_from(list(MyEnum))              # Choose from enum
st.sampled_from(range(10))                 # Choose from range
```

### One Of (Union)
```python
st.one_of(st.integers(), st.text())        # int OR str
st.one_of(st.none(), st.integers())        # Optional int
st.integers() | st.text()                  # Shorthand for one_of
```

### Just (Constant)
```python
st.just(42)                                # Always 42
st.just(None)                              # Always None
```

## Building Complex Objects

### Using builds()
```python
# Simple class
st.builds(User)                            # Infers from type hints

# Explicit arguments
st.builds(User,
    name=st.text(min_size=1),
    email=st.emails()
)

# Partial arguments (rest from hints)
st.builds(Order, items=st.lists(item_strategy()))
```

### Using @composite
```python
@st.composite
def user_strategy(draw):
    """Generate valid User objects."""
    name = draw(st.text(min_size=1, max_size=100))
    age = draw(st.integers(min_value=0, max_value=150))

    # Conditional logic
    if age < 18:
        account_type = 'minor'
    else:
        account_type = draw(st.sampled_from(['free', 'premium']))

    return User(name=name, age=age, account_type=account_type)

@st.composite
def order_with_items(draw, min_items=1, max_items=10):
    """Parameterized composite strategy."""
    items = draw(st.lists(
        item_strategy(),
        min_size=min_items,
        max_size=max_items
    ))
    discount = draw(st.floats(min_value=0, max_value=0.5))
    return Order(items=items, discount=discount)
```

## Specialized Strategies

### Email and URLs
```python
st.emails()                                # Valid email addresses
# Note: For URLs, use from_regex or custom composite
```

### Dates and Times
```python
st.dates()                                 # datetime.date
st.dates(min_value=date(2020, 1, 1))       # Bounded dates
st.times()                                 # datetime.time
st.datetimes()                             # datetime.datetime
st.datetimes(timezones=st.timezones())     # Timezone-aware
st.timedeltas()                            # datetime.timedelta
```

### UUIDs
```python
st.uuids()                                 # UUID objects
st.uuids(version=4)                        # Specific version
```

### Decimals
```python
st.decimals()                              # decimal.Decimal
st.decimals(min_value=0, max_value=100, places=2)  # Money-like
st.decimals(allow_nan=False, allow_infinity=False)
```

## Transformation Strategies

### Map (Transform Values)
```python
st.integers().map(str)                     # Convert int to str
st.integers().map(lambda x: x * 2)         # Double all values
st.text().map(str.strip)                   # Strip whitespace
```

### Filter
```python
st.integers().filter(lambda x: x % 2 == 0)  # Even only
st.text().filter(lambda s: len(s) > 0)      # Non-empty
# Note: Prefer constrained strategies over filter when possible
```

### FlatMap (Dependent Strategies)
```python
# Generate list, then element from that list
st.lists(st.integers(), min_size=1).flatmap(
    lambda lst: st.tuples(st.just(lst), st.sampled_from(lst))
)
```

## Recursive Strategies

### For Tree-like Structures
```python
# JSON-like structure
json_strategy = st.recursive(
    # Base case: primitives
    st.none() | st.booleans() | st.floats(allow_nan=False) | st.text(),
    # Recursive case: extend with collections
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=50
)

# Binary tree
@st.composite
def tree_strategy(draw, max_depth=5):
    if max_depth == 0 or draw(st.booleans()):
        return Leaf(draw(st.integers()))
    else:
        left = draw(tree_strategy(max_depth=max_depth-1))
        right = draw(tree_strategy(max_depth=max_depth-1))
        return Node(left, right)
```

## Strategy Modifiers

### Examples (Explicit Values)
```python
st.integers().example()                    # Get one example (for debugging)

# Force specific examples to always be tried
@given(st.integers())
@example(0)          # Always test 0
@example(-1)         # Always test -1
@example(MAX_INT)    # Always test boundary
def test_with_explicit_examples(n): ...
```

## Data Strategy (Draw in Test)
```python
@given(st.data())
def test_with_dynamic_draw(data):
    # Generate values dynamically based on test logic
    n = data.draw(st.integers(min_value=1, max_value=100))
    lst = data.draw(st.lists(st.integers(), min_size=n, max_size=n))
    assert len(lst) == n
```

## Common Patterns

### Non-Empty Collections
```python
st.lists(st.integers(), min_size=1)        # Non-empty list
st.text(min_size=1)                        # Non-empty string
st.dictionaries(st.text(), st.integers(), min_size=1)
```

### Bounded Numbers
```python
st.integers(min_value=0)                   # Non-negative
st.integers(min_value=1)                   # Positive
st.floats(min_value=0.0, exclude_min=True) # Strictly positive
```

### Optional Values
```python
st.none() | st.integers()                  # None or int
st.one_of(st.none(), st.text(min_size=1))  # None or non-empty string
```

### Domain-Specific
```python
# Positive money amounts
money = st.decimals(min_value=Decimal('0.01'), max_value=Decimal('10000'), places=2)

# Percentage (0-100)
percentage = st.floats(min_value=0, max_value=100, allow_nan=False)

# Valid usernames
username = st.from_regex(r'[a-z][a-z0-9_]{2,19}', fullmatch=True)

# Port numbers
port = st.integers(min_value=1, max_value=65535)
```
