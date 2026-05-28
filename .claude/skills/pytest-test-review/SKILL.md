---
name: pytest-test-review
description: "Use when: (1) Reviewing test code in PRs, (2) Evaluating test quality or coverage, (3) Identifying test anti-patterns, (4) Assessing if tests follow unit/integration/acceptance patterns, (5) Checking mock usage appropriateness, (6) Questions about test design."
---

# Pytest Test Review Skill

Review pytest tests against established quality principles: Kent Beck's Test Desiderata and GOOS (Growing Object-Oriented Software) practices.

## Review Process

### 1. Classify the Test Type
Determine which layer the test belongs to:

| Type | Purpose | Key Signals |
|------|---------|-------------|
| **Unit** | One object's behavior in isolation | No DB/network, mocked collaborators, millisecond speed |
| **Integration** | Adapter correctness at boundaries | Real DB/infrastructure, tests one boundary |
| **Acceptance** | User-visible behavior end-to-end | HTTP client, real URLs, full slice |

If misclassified, flag immediately—wrong layer means wrong review criteria.

### 2. Apply the 12 Test Properties

Evaluate against Kent Beck's Test Desiderata. Not all properties apply equally—identify trade-offs.

| Property | Quick Check |
|----------|-------------|
| **Behavioral** | Fails when behavior breaks? |
| **Structure-insensitive** | Survives refactoring? |
| **Readable** | Understandable without reading implementation? |
| **Writable** | Setup proportional to assertion? |
| **Fast** | Runs in CI without delays? |
| **Deterministic** | Always same result? No time/random flakiness? |
| **Automated** | Clear pass/fail, no manual inspection? |
| **Isolated** | Runs in any order? Cleans up after itself? |
| **Composable** | Tests concerns separately, not N×M combinations? |
| **Specific** | Failure points to specific problem? |
| **Predictive** | Passing predicts production success? |
| **Inspiring** | Gives confidence to change code? |

### 3. Check Test Structure

Every test should follow clear structure:

```python
def test_describes_behavior_in_domain_terms():
    # Arrange / Given
    ...
    # Act / When
    ...
    # Assert / Then
    ...
```

**Red flags:**
- Missing or trivial assertions
- Multiple unrelated behaviors in one test
- Test name describes implementation, not behavior
- Setup dwarfs the actual test

### 4. Evaluate Mocking

**Appropriate mocking:**
- Isolating object under test from collaborators
- Mocking roles/interfaces you own
- Verifying messages sent to collaborators

**Inappropriate mocking:**
- Mocking value objects or data structures
- Mocking third-party libraries directly (wrap in adapter first)
- Deep mock chains (mock → mock → mock)
- Mocking the subject under test

Always verify mocks are actually called:
```python
# ✗ Bad: mock exists but never verified
mock_sender = mocker.patch("module.sender")
service.notify(user)

# ✓ Good: verify the interaction
mock_sender.send.assert_called_once_with(to=user.email)
```

### 5. Listen to Test Pain

Difficult tests signal design problems in the code, not the test:

| Test Pain | Likely Code Problem |
|-----------|---------------------|
| Hard to set up | Too many responsibilities |
| Must mock value objects | Behavior/data not separated |
| Must mock concrete classes | Missing interface abstraction |
| Complex verification | Too much internal state exposed |
| Tests break on refactor | Over-specified implementation |

## Type-Specific Review

### Unit Tests
See [references/unit-test-checklist.md](references/unit-test-checklist.md) for detailed checklist.

**Essential criteria:**
- Tests single behavior of single object
- No I/O (DB, network, filesystem)
- Runs in milliseconds
- Mocks only roles, not concrete classes
- Assertions on public behavior only

### Integration Tests
See [references/integration-test-checklist.md](references/integration-test-checklist.md) for detailed checklist.

**Essential criteria:**
- Tests single boundary (repository, adapter)
- Uses real infrastructure, not mocks
- Controlled fakes for external services
- Assertions on real side effects

### Acceptance Tests
See [references/acceptance-test-checklist.md](references/acceptance-test-checklist.md) for detailed checklist.

**Essential criteria:**
- Uses HTTP client as only entry point
- Tests user-visible behavior
- No mocks for framework internals
- One user story per test

## Common Anti-Patterns

Flag these immediately:

| Anti-Pattern | Problem |
|--------------|---------|
| No assertions | Test proves nothing |
| Mocking what you test | Circular logic |
| Shared mutable state | Order-dependent tests |
| Testing framework code | Wasted effort |
| Magic numbers without context | Unclear intent |
| `time.sleep()` in tests | Flaky, slow |

See [references/anti-patterns.md](references/anti-patterns.md) for comprehensive list.

## Review Output Format

Structure feedback as:

```markdown
## Test Review: [file/test name]

### Classification
[Unit/Integration/Acceptance] - [Correct/Misclassified]

### Strengths
- ...

### Issues
1. **[Property violated]**: [Specific problem]
   - Location: [line/function]
   - Suggestion: [How to fix]

### Recommendations
- ...
```

## Quick Decision Tree

```
Is there a test?
  No → Request test coverage

Does test have assertions?
  No → Flag: test proves nothing

Can you understand intent from name + structure?
  No → Request clearer naming/structure

Does it test one thing?
  No → Request split into focused tests

Is mocking appropriate for test type?
  No → Flag mocking issue with specific guidance

Would this test catch the bug it's meant to prevent?
  No → Flag: test may not be predictive
```

## Related Skills

This skill reviews tests written using:

- **[pytest-unit-tests](../pytest-unit-tests/SKILL.md)**: Unit test patterns and principles
- **[pytest-integration-tests](../pytest-integration-tests/SKILL.md)**: Integration test patterns for boundaries
- **[pytest-acceptance-tests](../pytest-acceptance-tests/SKILL.md)**: Acceptance test patterns for user workflows
- **[pytest-fixtures](../pytest-fixtures/SKILL.md)**: Fixture patterns and organization
- **[pytest-mocking](../pytest-mocking/SKILL.md)**: Mocking patterns and best practices
