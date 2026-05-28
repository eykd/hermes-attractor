# Model-Based Stateful Testing

Test stateful systems by defining a model and verifying implementation matches it.

## When to Use Stateful Testing

- Testing systems with state (databases, caches, queues)
- APIs where operation order matters
- Data structures with multiple operations
- Systems where bugs emerge from operation sequences

## RuleBasedStateMachine

The core abstraction for stateful testing.

### Basic Structure

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, initialize

class MyStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        # Initialize system under test
        self.system = MySystem()
        # Initialize reference model
        self.model = {}

    @rule(key=st.text(), value=st.integers())
    def add_item(self, key, value):
        """Test adding items."""
        self.system.add(key, value)
        self.model[key] = value

    @rule(key=st.text())
    def remove_item(self, key):
        """Test removing items."""
        if key in self.model:
            self.system.remove(key)
            del self.model[key]

    @invariant()
    def model_matches_system(self):
        """Verify system matches model after every operation."""
        assert dict(self.system.items()) == self.model

# Create test class
TestMySystem = MyStateMachine.TestCase
```

### Rules

Rules define operations that can be performed:

```python
class ShoppingCartMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.cart = ShoppingCart()
        self.expected_items = {}

    @rule(item=item_strategy(), quantity=st.integers(min_value=1, max_value=10))
    def add_item(self, item, quantity):
        self.cart.add(item, quantity)
        self.expected_items[item.id] = self.expected_items.get(item.id, 0) + quantity

    @rule(item_id=st.text())
    def remove_item(self, item_id):
        if item_id in self.expected_items:
            self.cart.remove(item_id)
            del self.expected_items[item_id]

    @rule()
    def clear_cart(self):
        self.cart.clear()
        self.expected_items.clear()
```

### Preconditions

Restrict when rules can fire:

```python
class QueueMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.queue = Queue()
        self.model = []

    @rule(item=st.integers())
    def enqueue(self, item):
        self.queue.enqueue(item)
        self.model.append(item)

    @precondition(lambda self: len(self.model) > 0)
    @rule()
    def dequeue(self):
        """Only dequeue when queue is non-empty."""
        result = self.queue.dequeue()
        expected = self.model.pop(0)
        assert result == expected

    @precondition(lambda self: len(self.model) > 0)
    @rule()
    def peek(self):
        result = self.queue.peek()
        assert result == self.model[0]
```

### Bundles (Generated References)

Use bundles to reference previously created objects:

```python
from hypothesis.stateful import Bundle, consumes

class DatabaseMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.model = {}

    # Bundle stores created record IDs
    records = Bundle('records')

    @rule(target=records, data=st.dictionaries(st.text(), st.text()))
    def create_record(self, data):
        """Create record and store ID in bundle."""
        record_id = self.db.create(data)
        self.model[record_id] = data
        return record_id  # Added to 'records' bundle

    @rule(record_id=records)
    def read_record(self, record_id):
        """Read using ID from bundle."""
        result = self.db.read(record_id)
        assert result == self.model[record_id]

    @rule(record_id=records, data=st.dictionaries(st.text(), st.text()))
    def update_record(self, record_id, data):
        self.db.update(record_id, data)
        self.model[record_id] = data

    @rule(record_id=consumes(records))  # consumes removes from bundle
    def delete_record(self, record_id):
        self.db.delete(record_id)
        del self.model[record_id]
```

### Invariants

Checked after every rule execution:

```python
class BalancedTreeMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.tree = AVLTree()
        self.items = set()

    @rule(value=st.integers())
    def insert(self, value):
        self.tree.insert(value)
        self.items.add(value)

    @rule(value=st.integers())
    def delete(self, value):
        if value in self.items:
            self.tree.delete(value)
            self.items.discard(value)

    @invariant()
    def tree_is_balanced(self):
        """AVL property: heights differ by at most 1."""
        assert self.tree.is_balanced()

    @invariant()
    def tree_is_sorted(self):
        """BST property: in-order traversal is sorted."""
        values = list(self.tree.inorder())
        assert values == sorted(values)

    @invariant()
    def contains_all_items(self):
        """Tree contains exactly the items we added."""
        assert set(self.tree.inorder()) == self.items
```

### Initialize

Set up initial state before rules run:

```python
class AccountMachine(RuleBasedStateMachine):
    accounts = Bundle('accounts')

    @initialize(target=accounts, balance=st.floats(min_value=0, max_value=10000))
    def create_initial_account(self, balance):
        """Create at least one account before other rules."""
        account_id = self.bank.create_account(balance)
        self.model[account_id] = balance
        return account_id

    @rule(target=accounts, balance=st.floats(min_value=0, max_value=10000))
    def create_account(self, balance):
        account_id = self.bank.create_account(balance)
        self.model[account_id] = balance
        return account_id
```

## Complete Example: Key-Value Store

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, precondition
from hypothesis import strategies as st

class KeyValueStoreMachine(RuleBasedStateMachine):
    """Test a key-value store against a dict model."""

    def __init__(self):
        super().__init__()
        self.store = KeyValueStore()  # System under test
        self.model = {}                # Reference model

    @rule(key=st.text(max_size=10), value=st.integers())
    def set_value(self, key, value):
        self.store.set(key, value)
        self.model[key] = value

    @rule(key=st.text(max_size=10))
    def get_value(self, key):
        store_result = self.store.get(key)
        model_result = self.model.get(key)
        assert store_result == model_result

    @rule(key=st.text(max_size=10))
    def delete_value(self, key):
        self.store.delete(key)
        self.model.pop(key, None)

    @rule(key=st.text(max_size=10))
    def contains(self, key):
        assert self.store.contains(key) == (key in self.model)

    @rule()
    def clear(self):
        self.store.clear()
        self.model.clear()

    @rule()
    def size(self):
        assert self.store.size() == len(self.model)

    @invariant()
    def size_matches(self):
        assert self.store.size() == len(self.model)

    @invariant()
    def keys_match(self):
        assert set(self.store.keys()) == set(self.model.keys())

# This creates the actual pytest test
TestKeyValueStore = KeyValueStoreMachine.TestCase
```

## Complete Example: Bank Account

```python
class BankAccountMachine(RuleBasedStateMachine):
    """Test bank account with transfers between accounts."""

    accounts = Bundle('accounts')

    def __init__(self):
        super().__init__()
        self.bank = Bank()
        self.balances = {}

    @initialize(target=accounts, initial=st.floats(min_value=100, max_value=10000))
    def create_first_account(self, initial):
        acc_id = self.bank.create_account(initial)
        self.balances[acc_id] = initial
        return acc_id

    @rule(target=accounts, initial=st.floats(min_value=0, max_value=10000))
    def create_account(self, initial):
        acc_id = self.bank.create_account(initial)
        self.balances[acc_id] = initial
        return acc_id

    @rule(account=accounts, amount=st.floats(min_value=0.01, max_value=1000))
    def deposit(self, account, amount):
        self.bank.deposit(account, amount)
        self.balances[account] += amount

    @precondition(lambda self: any(b >= 0.01 for b in self.balances.values()))
    @rule(account=accounts, amount=st.floats(min_value=0.01, max_value=100))
    def withdraw(self, account, amount):
        if self.balances[account] >= amount:
            self.bank.withdraw(account, amount)
            self.balances[account] -= amount

    @precondition(lambda self: len(self.balances) >= 2)
    @rule(
        source=accounts,
        dest=accounts,
        amount=st.floats(min_value=0.01, max_value=100)
    )
    def transfer(self, source, dest, amount):
        if source != dest and self.balances[source] >= amount:
            self.bank.transfer(source, dest, amount)
            self.balances[source] -= amount
            self.balances[dest] += amount

    @invariant()
    def balances_non_negative(self):
        for acc_id in self.balances:
            assert self.bank.get_balance(acc_id) >= 0

    @invariant()
    def balances_match_model(self):
        for acc_id, expected in self.balances.items():
            actual = self.bank.get_balance(acc_id)
            assert abs(actual - expected) < 0.01, f"{acc_id}: {actual} != {expected}"

TestBankAccount = BankAccountMachine.TestCase
```

## Running Stateful Tests

```bash
# Run normally
pytest test_stateful.py -v

# See step sequences
pytest test_stateful.py -v --hypothesis-show-statistics

# Increase examples
pytest test_stateful.py --hypothesis-seed=0
```

## Debugging Failures

When a stateful test fails, Hypothesis prints the sequence of operations:

```
state = MyMachine()
state.add_item(key='x', value=1)
state.add_item(key='y', value=2)
state.remove_item(key='x')
state.add_item(key='x', value=3)  # Failure occurs here
```

This helps reproduce and debug the exact sequence that caused the failure.

## Best Practices

1. **Keep models simple** — Model should be obviously correct
2. **Test one system** — Don't test multiple interacting systems
3. **Use preconditions** — Prevent invalid operation sequences
4. **Add invariants** — Catch violations immediately
5. **Use bundles** — For referencing created objects
6. **Start small** — Begin with few rules, add complexity gradually
