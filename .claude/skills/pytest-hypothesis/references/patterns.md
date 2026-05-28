# Property Patterns and Real-World Examples

Proven patterns for property-based testing organized by domain and property type.

## Property Types

### 1. Roundtrip Properties
Test that encoding/decoding returns original value.

```python
# Serialization
@given(st.builds(User, name=st.text(), age=st.integers(min_value=0)))
def test_json_roundtrip(user):
    assert User.from_json(user.to_json()) == user

# Encoding
@given(st.text())
def test_base64_roundtrip(text):
    encoded = base64.b64encode(text.encode())
    decoded = base64.b64decode(encoded).decode()
    assert decoded == text

# Compression
@given(st.binary())
def test_gzip_roundtrip(data):
    compressed = gzip.compress(data)
    decompressed = gzip.decompress(compressed)
    assert decompressed == data

# Database operations
@given(user_strategy())
def test_db_roundtrip(db, user):
    user_id = db.save(user)
    retrieved = db.get(user_id)
    assert retrieved == user
```

### 2. Invariant Properties
Properties that must always hold regardless of input.

```python
# Length preservation
@given(st.lists(st.integers()))
def test_sort_preserves_length(lst):
    assert len(sorted(lst)) == len(lst)

# Element preservation
@given(st.lists(st.integers()))
def test_sort_preserves_elements(lst):
    assert set(sorted(lst)) == set(lst)

# Ordering
@given(st.lists(st.integers()))
def test_sort_is_ordered(lst):
    result = sorted(lst)
    for i in range(len(result) - 1):
        assert result[i] <= result[i + 1]

# Non-negative results
@given(st.lists(st.floats(allow_nan=False), min_size=1))
def test_variance_non_negative(data):
    assert variance(data) >= 0

# Bounds
@given(st.lists(st.integers(), min_size=1))
def test_mean_within_bounds(data):
    assert min(data) <= mean(data) <= max(data)
```

### 3. Idempotence Properties
Applying operation multiple times equals applying once.

```python
@given(st.text())
def test_strip_idempotent(s):
    assert s.strip().strip() == s.strip()

@given(st.lists(st.integers()))
def test_sort_idempotent(lst):
    assert sorted(sorted(lst)) == sorted(lst)

@given(st.lists(st.integers()))
def test_dedupe_idempotent(lst):
    assert dedupe(dedupe(lst)) == dedupe(lst)

@given(st.text())
def test_normalize_idempotent(s):
    assert normalize(normalize(s)) == normalize(s)
```

### 4. Commutativity and Associativity
Order of operations doesn't matter.

```python
# Commutativity
@given(st.integers(), st.integers())
def test_add_commutative(a, b):
    assert a + b == b + a

@given(st.sets(st.integers()), st.sets(st.integers()))
def test_union_commutative(a, b):
    assert a | b == b | a

# Associativity
@given(st.integers(), st.integers(), st.integers())
def test_add_associative(a, b, c):
    assert (a + b) + c == a + (b + c)

@given(st.lists(st.integers()), st.lists(st.integers()), st.lists(st.integers()))
def test_concat_associative(a, b, c):
    assert (a + b) + c == a + (b + c)
```

### 5. Oracle Properties
Compare against a trusted reference implementation.

```python
@given(st.lists(st.integers()))
def test_my_sort_matches_builtin(lst):
    assert my_sort(lst) == sorted(lst)

@given(st.integers(min_value=0))
def test_my_factorial_matches_math(n):
    assume(n <= 20)  # Avoid overflow
    assert my_factorial(n) == math.factorial(n)

@given(st.text(), st.text())
def test_my_distance_matches_library(s1, s2):
    assert my_levenshtein(s1, s2) == editdistance.eval(s1, s2)
```

### 6. Metamorphic Properties
Relationship between outputs for related inputs.

```python
# Scaling
@given(st.lists(st.floats(allow_nan=False, allow_infinity=False), min_size=1))
def test_mean_scales_linearly(data):
    k = 2
    scaled_data = [x * k for x in data]
    assert abs(mean(scaled_data) - k * mean(data)) < 1e-10

# Monotonicity
@given(st.integers(), st.integers(min_value=0))
def test_factorial_monotonic(n, delta):
    assume(n >= 0 and n + delta <= 20)
    assert factorial(n) <= factorial(n + delta)

# Size relationship
@given(st.sets(st.integers()), st.sets(st.integers()))
def test_intersection_subset_of_inputs(a, b):
    intersection = a & b
    assert intersection <= a
    assert intersection <= b
```

## Domain-Specific Patterns

### String Processing

```python
@given(st.text())
def test_uppercase_length_preserved(s):
    assert len(s.upper()) == len(s)

@given(st.text())
def test_split_join_roundtrip(s):
    assert ''.join(s.split()) == s.replace(' ', '').replace('\t', '').replace('\n', '')

@given(st.text(), st.text())
def test_contains_after_concat(a, b):
    combined = a + b
    assert a in combined and b in combined
```

### Numeric Operations

```python
@given(st.floats(allow_nan=False, allow_infinity=False))
def test_abs_non_negative(x):
    assert abs(x) >= 0

@given(st.floats(min_value=0, allow_infinity=False))
def test_sqrt_squares_back(x):
    assert abs(math.sqrt(x) ** 2 - x) < 1e-10

@given(st.integers(min_value=1))
def test_log_exp_inverse(x):
    assert abs(math.exp(math.log(x)) - x) < 1e-10
```

### Data Structures

```python
# Stack
@given(st.lists(st.integers()))
def test_stack_lifo(items):
    stack = Stack()
    for item in items:
        stack.push(item)

    popped = [stack.pop() for _ in items]
    assert popped == list(reversed(items))

# Queue
@given(st.lists(st.integers()))
def test_queue_fifo(items):
    queue = Queue()
    for item in items:
        queue.enqueue(item)

    dequeued = [queue.dequeue() for _ in items]
    assert dequeued == items

# Dictionary
@given(st.dictionaries(st.text(), st.integers()))
def test_dict_keys_values_match(d):
    assert len(d.keys()) == len(d.values()) == len(d)
    for k in d.keys():
        assert k in d
```

### API/Web

```python
# REST endpoint
@given(st.builds(CreateUserRequest, name=st.text(min_size=1), email=st.emails()))
def test_create_user_returns_id(client, request):
    response = client.post('/users', json=request.dict())
    assert response.status_code == 201
    assert 'id' in response.json()

# Query parameters
@given(st.integers(min_value=1, max_value=100), st.integers(min_value=0))
def test_pagination_bounds(client, limit, offset):
    response = client.get(f'/items?limit={limit}&offset={offset}')
    assert len(response.json()['items']) <= limit

# Filtering
@given(st.lists(st.builds(Item, price=st.floats(min_value=0, max_value=1000))))
def test_filter_returns_subset(items, min_price):
    filtered = filter_by_price(items, min_price=min_price)
    assert all(item.price >= min_price for item in filtered)
    assert set(filtered) <= set(items)
```

### Financial/Business Logic

```python
# Price calculations
@given(
    st.floats(min_value=0.01, max_value=10000),
    st.floats(min_value=0, max_value=1)
)
def test_discount_reduces_price(price, discount_rate):
    discounted = apply_discount(price, discount_rate)
    assert discounted <= price
    assert discounted >= 0

# Order totals
@given(st.lists(
    st.builds(LineItem,
        quantity=st.integers(min_value=1, max_value=100),
        unit_price=st.decimals(min_value=Decimal('0.01'), max_value=Decimal('1000'), places=2)
    ),
    min_size=1
))
def test_order_total_positive(items):
    order = Order(items=items)
    assert order.total() > 0
    assert order.total() == sum(i.quantity * i.unit_price for i in items)

# Tax calculations
@given(st.decimals(min_value=Decimal('0'), max_value=Decimal('10000'), places=2))
def test_tax_non_negative(amount):
    tax = calculate_tax(amount)
    assert tax >= 0
    assert tax <= amount  # Tax shouldn't exceed amount
```

### Parsing

```python
# JSON parsing
@given(st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(),
    lambda children: st.lists(children) | st.dictionaries(st.text(), children)
))
def test_json_roundtrip(data):
    serialized = json.dumps(data)
    deserialized = json.loads(serialized)
    assert deserialized == data

# Config parsing
@given(config_strategy())
def test_config_parse_valid(config):
    serialized = config.to_yaml()
    parsed = Config.from_yaml(serialized)
    assert parsed == config

# Date parsing
@given(st.dates())
def test_date_format_roundtrip(date):
    formatted = date.strftime('%Y-%m-%d')
    parsed = datetime.strptime(formatted, '%Y-%m-%d').date()
    assert parsed == date
```

## Combining Properties

Test multiple properties in one suite:

```python
class TestSorting:
    @given(st.lists(st.integers()))
    def test_preserves_length(self, lst):
        assert len(sorted(lst)) == len(lst)

    @given(st.lists(st.integers()))
    def test_preserves_elements(self, lst):
        assert sorted(sorted(lst)) == sorted(lst)

    @given(st.lists(st.integers()))
    def test_is_ordered(self, lst):
        result = sorted(lst)
        assert all(result[i] <= result[i+1] for i in range(len(result)-1))

    @given(st.lists(st.integers()))
    def test_idempotent(self, lst):
        assert sorted(sorted(lst)) == sorted(lst)
```

## Edge Cases to Consider

When writing property tests, ensure strategies can generate:
- Empty collections
- Single-element collections
- Duplicate values
- Boundary values (0, -1, MAX_INT)
- Unicode edge cases (empty string, whitespace only, surrogate pairs)
- Floating point edge cases (very small, very large, negative zero)
