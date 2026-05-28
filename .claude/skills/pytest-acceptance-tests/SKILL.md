---
name: pytest-acceptance-tests
description: "Use when: (1) Testing complete user workflows via HTTP/CLI, (2) Testing user-visible behavior end-to-end, (3) Implementing outside-in TDD, (4) Converting feature specs to executable tests, (5) Questions about acceptance test design. Two approaches: HTTP client (fast) or BDD with Gherkin (stakeholder-friendly)."
---

# Pytest Acceptance Tests Skill

Write acceptance tests that describe user-visible behavior, drive outside-in design, and remain stable through refactoring.

This skill covers **two complementary approaches** to acceptance testing:

1. **HTTP Client Approach** (pytest + Django test client): Fast, direct Python tests using Given-When-Then structure
2. **BDD Approach** (pytest-bdd + Gherkin): Feature files with executable scenarios, great for stakeholder collaboration

## Core Definition

> An acceptance test is an executable story of user-visible behavior that uses real infrastructure, describes a single user story in Given—When—Then form, asserts only on observable outcomes, and remains ignorant of implementation details.

## Choosing Your Approach

### HTTP Client Approach (Recommended for most cases)

**Use when:**
- You want fast test execution
- Your team is comfortable with Python
- You don't need stakeholder collaboration on test scenarios
- JavaScript interactions aren't critical

**Characteristics:**
- ✅ Fast execution (no browser overhead)
- ✅ Direct database and HTTP testing
- ✅ Simple setup and debugging
- ✅ Good for server-rendered HTML
- ❌ No JavaScript execution
- ❌ Tests live in Python code, not natural language

### BDD Approach (pytest-bdd + Gherkin)

**Use when:**
- Non-technical stakeholders need to read/contribute to scenarios
- You want executable specifications (living documentation)
- Complex user workflows benefit from Gherkin's expressiveness
- You need browser-based testing (Selenium/Splinter)

**Characteristics:**
- ✅ Natural language scenarios (stakeholder-friendly)
- ✅ Feature files serve as living documentation
- ✅ Browser testing with pytest-splinter (JavaScript support)
- ✅ Reusable step definitions
- ❌ Slower execution (especially with browser)
- ❌ More setup required
- ❌ Extra layer of indirection

**Quick Decision:** If in doubt, start with the HTTP Client approach. It's simpler and faster. Move to BDD when you need stakeholder collaboration or browser testing.

## When to Write Acceptance Tests

```
Is this testing user-visible behavior?
├── No → Consider unit or integration test
└── Yes → Does it exercise the full system path?
    ├── No → Consider integration test
    └── Yes → Write acceptance test
```

## Directory Structure

### HTTP Client Approach

```
tests/
├── conftest.py              # Shared fixtures
├── acceptance/              # Acceptance tests
│   ├── conftest.py          # Acceptance-specific fixtures
│   ├── test_<feature>_acceptance.py
│   └── ...
├── integration/             # Boundary/adapter tests
└── unit/                    # Object behavior tests
```

### BDD Approach (pytest-bdd)

```
tests/
├── conftest.py              # Shared fixtures
├── acceptance/              # Acceptance tests
│   ├── conftest.py          # Browser & BDD fixtures
│   ├── features/            # Gherkin feature files
│   │   ├── login.feature
│   │   ├── checkout.feature
│   │   └── ...
│   └── step_defs/           # Step implementations
│       ├── common_steps.py  # Reusable steps
│       ├── test_login.py
│       └── test_checkout.py
├── integration/
└── unit/
```

---

# Approach 1: HTTP Client Testing

## Essential Structure: Given-When-Then

Every acceptance test follows this pattern:

```python
# tests/acceptance/test_checkout_acceptance.py
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_user_can_complete_checkout(client, user_factory, product_factory):
    """Logged-in user can purchase items in their cart."""

    # GIVEN: A logged-in user with items in cart
    user = user_factory()
    product = product_factory(name="Widget", price=25.00)
    client.force_login(user)
    client.post(reverse("cart:add"), data={"product_id": product.id})

    # WHEN: User completes checkout
    response = client.post(reverse("checkout"), data={
        "shipping_address": "123 Main St",
        "payment_method": "card",
    })

    # THEN: Order is created and user is redirected
    assert response.status_code == 302
    assert reverse("order:confirmation") in response["Location"]
    assert Order.objects.filter(user=user).exists()
```

## Must/Must Not Rules

### Acceptance Tests MUST:
- Use HTTP layer (`client`) as entry point
- Hit real URL patterns via `reverse()`
- Touch real database and templates
- Assert on user-visible outcomes
- Test exactly one user story

### Acceptance Tests MUST NOT:
- Call views, forms, or services directly
- Mock Django/framework internals
- Assert on internal context keys
- Test multiple unrelated behaviors
- Depend on test execution order

## Fixture Patterns for Acceptance Tests

Acceptance tests typically use factory fixtures and composite state fixtures to set up user workflows.

```python
@pytest.fixture
def logged_in_client(client, user_factory):
    user = user_factory()
    client.force_login(user)
    client.user = user
    return client
```

For comprehensive fixture patterns (factory fixtures, composition, scopes), see **[pytest-fixtures](../pytest-fixtures/SKILL.md)**.

## Assertion Guidelines

| Always Assert | Never Assert |
|---------------|--------------|
| HTTP status codes | Exact HTML structure |
| Redirect locations | Internal context keys |
| Key user-visible content | Implementation details |
| Essential DB state changes | Log messages |
| Error messages shown to user | Method call sequences |

## Naming Conventions

```python
# File: test_<feature>_acceptance.py
# Function: test_<actor>_can_<action>_<context>()

def test_user_can_register_with_valid_email(): ...
def test_guest_is_redirected_when_accessing_dashboard(): ...
def test_admin_can_delete_user_account(): ...
def test_checkout_fails_with_invalid_payment(): ...
```

## Determinism Checklist

- [ ] No `datetime.now()` — use `freezegun` or pass time explicitly
- [ ] No random data — use fixed test values
- [ ] No order dependencies — each test runs in isolation
- [ ] Transactions roll back — use `pytest.mark.django_db`

## Common Anti-Patterns

| Anti-Pattern | Fix |
|--------------|-----|
| God test (tests entire flow) | Split into separate user stories |
| Mocking framework internals | Use real infrastructure |
| Asserting implementation | Assert observable outcomes |
| Fragile HTML assertions | Assert key content, not structure |
| Setup in test body | Extract to fixtures |

## Test Desiderata for Acceptance Tests

Acceptance tests embody Kent Beck's Test Desiderata principles:

| Property | In Acceptance Tests |
|----------|---------------------|
| Behavioral | Fails if feature breaks |
| Structure-insensitive | Passes after refactoring |
| Readable | Reads like user story |
| Fast | Use transactions, scope fixtures |
| Deterministic | Control time, no random data |
| Isolated | Independent of other tests |
| Composable | One story per test |
| Specific | Clear failure messages |
| Predictive | Uses real infrastructure |
| Inspiring | Enables confident deploys |

For complete Test Desiderata guidance, see **[pytest-unit-tests/references/test-desiderata.md](../pytest-unit-tests/references/test-desiderata.md)**.

## When to Use This Skill

**Choose pytest-acceptance-tests when:**
- Testing complete user workflows from start to finish
- Entry point is HTTP client (`client.post()`) or CLI command
- Verifying user-visible behavior and outcomes
- Implementing outside-in TDD (write acceptance test first, then work inward)
- Testing full system integration (routing, views, forms, database, templates)

**Use a different skill when:**
- Testing single adapter or boundary → **pytest-integration-tests**
- Testing business logic without infrastructure → **pytest-unit-tests**
- Need fixture patterns → **pytest-fixtures**
- Testing async views or workflows → **pytest-async-testing**

## Quick Decision Guide: Is This an Acceptance Test?

**✅ Write an acceptance test when:**
- Entry point is HTTP endpoint or CLI command
- Testing complete user story (login → add to cart → checkout)
- Asserting on user-visible outcomes (status codes, redirects, page content)
- Using real database, templates, and routing

**❌ Not an acceptance test when:**
- Testing one repository or adapter → Use **pytest-integration-tests**
- Testing domain logic → Use **pytest-unit-tests**
- Calling views/services directly → Refactor to use HTTP client

## GOOS Principles for Acceptance Tests

Acceptance tests follow Growing Object-Oriented Software (GOOS) principles:

1. **Write acceptance test first**: Describe the feature from user's perspective
2. **Test drives design**: Acceptance test reveals needed collaborators
3. **Outside-in development**: Start from HTTP layer, work toward domain
4. **Walking skeleton**: Build end-to-end infrastructure early
5. **Listen to tests**: Hard-to-test features often have design issues

The acceptance test defines "done" - when it passes, the feature is complete.

## Related Skills

Acceptance tests work with other testing layers:

- **[pytest-integration-tests](../pytest-integration-tests/SKILL.md)**: Test individual boundaries before full workflows
- **[pytest-unit-tests](../pytest-unit-tests/SKILL.md)**: Test business logic extracted during outside-in TDD
- **[pytest-fixtures](../pytest-fixtures/SKILL.md)**: Advanced fixture patterns for test data setup
- **[pytest-async-testing](../pytest-async-testing/SKILL.md)**: Testing async views and workflows
- **[django-pytest-patterns](../django-pytest-patterns/SKILL.md)**: Django-specific testing patterns, test client, and fixtures

## References

For deeper acceptance testing guidance:

- **[patterns.md](references/patterns.md)**: Detailed acceptance test patterns and examples
- **[desiderata.md](references/desiderata.md)**: Test Desiderata principles applied to acceptance tests
- **[django.md](references/django.md)**: Django-specific acceptance testing patterns

---

# Approach 2: BDD with pytest-bdd and Gherkin

The BDD approach uses Gherkin feature files (natural language scenarios) combined with Python step definitions. This creates executable specifications that non-technical stakeholders can read and validate.

## BDD Workflow

### Step 1: Understand the Feature Specification

Ask clarifying questions to understand:
- Who is the user/actor?
- What is the goal/capability?
- Why is this valuable (benefit)?
- What are the success criteria?
- What are the edge cases and error conditions?

If the user provides a feature specification document, extract the acceptance criteria. If not, help them define it using the Feature Spec JTBD skill if available.

### Step 2: Write Gherkin Scenarios

Create a `.feature` file in `tests/acceptance/features/` using the Gherkin syntax:

```gherkin
Feature: [Feature Name]
  As a [user role]
  I want to [capability]
  So that [benefit]

  Background:
    Given [common setup for all scenarios]

  Scenario: [Happy path scenario name]
    Given [initial context]
    When [action taken]
    Then [expected outcome]

  Scenario: [Error condition scenario name]
    Given [initial context]
    When [invalid action]
    Then [error handling]
```

**Key principles:**
- One scenario = one specific behavior
- Use concrete examples, not abstractions ("user@example.com" not "valid email")
- Test happy path, edge cases, and error conditions
- Keep scenarios focused (5-10 steps maximum)
- Use Background for common setup across scenarios
- Use Scenario Outline for data-driven testing

See **[references/gherkin-patterns.md](references/gherkin-patterns.md)** for detailed patterns and examples.

### Step 3: Set Up Test Infrastructure (if needed)

**Check if infrastructure exists:**
- Look for `pytest.ini`, `tests/acceptance/conftest.py`
- Check if pytest-bdd, pytest-django, pytest-splinter are installed

**If setting up from scratch**, run `scripts/setup_django_bdd.py`:

```bash
python .claude/skills/pytest-acceptance-tests/scripts/setup_django_bdd.py --project-root /path/to/project
```

This creates:
- `pytest.ini` with Django settings
- `tests/acceptance/` directory structure
- `conftest.py` with browser fixtures
- Requirements file with dependencies

**Manual setup alternative:** See **[references/manual-setup.md](references/manual-setup.md)**

### Step 4: Identify Required Fixtures

Analyze scenarios to determine needed fixtures:
- User models (regular users, admin users, users with specific permissions)
- Django model instances (Articles, Orders, Products, etc.)
- Browser state (authenticated vs anonymous)
- Test data (categories, tags, sample content)

Plan fixture scope:
- `function`: Clean state per test (default)
- `module`: Shared across test file
- `session`: Shared across entire test run

### Step 5: Write Step Definitions

Create step definition file in `tests/acceptance/step_defs/test_[feature_name].py`:

```python
from pytest_bdd import scenarios, given, when, then, parsers

# Bind all scenarios from feature file
scenarios('../features/[feature_name].feature')

# Given steps - setup
@given("I am logged in as an admin")
def admin_logged_in(browser, admin_user, live_server):
    browser.visit(f'{live_server.url}/admin/login/')
    browser.fill('username', admin_user.username)
    browser.fill('password', 'password')
    browser.find_by_css('button[type="submit"]').first.click()

# When steps - actions
@when(parsers.parse('I visit "{url}"'))
def visit_url(browser, live_server, url):
    browser.visit(f'{live_server.url}{url}')

# Then steps - assertions
@then(parsers.parse('I should see "{text}"'))
def see_text(browser, text):
    assert browser.is_text_present(text)
```

**Step implementation patterns:**
- Given: Use fixtures, create DB records, set browser state
- When: Browser interactions (visit, fill, click)
- Then: Assertions (is_text_present, check DB state)

See **[references/step-patterns.md](references/step-patterns.md)** for common patterns by domain (auth, forms, models, etc.)

### Step 6: Configure Browser Driver

**For fast tests without JavaScript:**
```python
@pytest.fixture(scope='session')
def splinter_webdriver():
    return 'django'  # Uses Django test client
```

**For JavaScript-heavy features:**
```python
@pytest.fixture(scope='session')
def splinter_webdriver():
    return 'chrome'  # Uses Chrome with Selenium
```

Django driver limitations: No JavaScript, screenshots, or window management. Use Chrome/Firefox for those features.

### Step 7: Run Tests

```bash
# Run all acceptance tests
pytest tests/acceptance/

# Run specific feature
pytest tests/acceptance/step_defs/test_login.py

# Run with verbose output
pytest -v tests/acceptance/

# Run tests matching a tag
pytest -m smoke

# Run and show print statements
pytest -s tests/acceptance/
```

### Step 8: Debug Failures

**Common debugging techniques:**

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Print HTML for inspection
print(browser.html)

# Print current URL
print(f"Current URL: {browser.url}")

# Check element exists
assert browser.is_element_present_by_css('.my-element', wait_time=5)

# Refresh model from DB
article.refresh_from_db()
```

**Common issues:**
- Element not found → Check selectors, ensure page loaded
- Stale object → Use `refresh_from_db()` on Django models
- Test pollution → Check fixture scopes, ensure DB rollback
- Live server issues → Ensure `live_server` fixture is used

See **[references/debugging.md](references/debugging.md)** for detailed troubleshooting guide.

## BDD Quick Reference

### Parsers

```python
from pytest_bdd import parsers

# Simple string parsing
@when(parsers.parse('I enter "{value}" in "{field}"'))
def enter_field(browser, value, field):
    browser.fill(field, value)

# Type conversion
@then(parsers.cfparse('the count should be {count:Number}'))
def check_count(browser, count):
    # count is automatically a number
    pass

# Regular expressions
@when(parsers.re(r'I wait (?P<seconds>\d+) seconds?'))
def wait(seconds):
    import time
    time.sleep(int(seconds))
```

### Django Test Client vs Browser

**Django driver (fast, no browser):**
- ✅ Fast execution
- ✅ Direct Django integration
- ✅ Good for server-rendered HTML
- ❌ No JavaScript execution
- ❌ No screenshots
- ❌ No complex interactions

**Chrome/Firefox (slower, real browser):**
- ✅ JavaScript execution
- ✅ Screenshots on failure
- ✅ Complex UI interactions
- ❌ Slower execution
- ❌ Requires browser driver setup

### Browser Interactions

```python
# Navigation
browser.visit('/products/')
browser.back()
browser.reload()

# Forms
browser.fill('email', 'user@example.com')
browser.check('accept_terms')      # Checkbox
browser.choose('color', 'blue')    # Radio
browser.select('country', 'US')    # Dropdown

# Finding elements
elem = browser.find_by_css('.title').first
elem = browser.find_by_id('submit')
elem = browser.find_by_name('username')
elem = browser.find_link_by_text('Login')

# Clicking
browser.find_by_id('submit').click()

# Checking content
assert browser.is_text_present('Success')
assert browser.is_element_present_by_css('.error')

# State
url = browser.url
html = browser.html
title = browser.title
```

## BDD Best Practices

1. **Scenario Quality**
   - Write from user perspective
   - Use concrete examples
   - One behavior per scenario
   - Test happy path + edge cases

2. **Step Reusability**
   - Create common steps in `common_steps.py`
   - Use parsers for parameterization
   - Share fixtures across tests

3. **Test Isolation**
   - Use function-scoped fixtures by default
   - Ensure database rollback between tests
   - Don't depend on test execution order

4. **Performance**
   - Use Django driver when possible
   - Share expensive fixtures (session scope)
   - Tag slow tests: `@slow`

5. **Maintainability**
   - Organize features by domain
   - Keep step definitions close to features
   - Document complex fixtures

## BDD Scripts

The skill includes helper scripts in the `scripts/` directory:

- **`setup_django_bdd.py`**: Initialize BDD test infrastructure for a Django project
- **`generate_step_skeleton.py`**: Generate step definitions from a .feature file

## BDD References

For comprehensive BDD patterns and examples:

- **[gherkin-patterns.md](references/gherkin-patterns.md)**: Extensive Gherkin scenario examples (auth, CRUD, forms, e-commerce, etc.)
- **[step-patterns.md](references/step-patterns.md)**: Reusable step definition patterns by domain
- **[complete-examples.md](references/complete-examples.md)**: Full working examples (blog, e-commerce) with all components
- **[debugging.md](references/debugging.md)**: BDD-specific debugging and troubleshooting
- **[manual-setup.md](references/manual-setup.md)**: Manual BDD infrastructure setup guide
