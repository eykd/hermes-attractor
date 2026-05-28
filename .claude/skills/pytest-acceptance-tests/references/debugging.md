# Debugging and Troubleshooting Guide

Comprehensive guide to debugging Django acceptance tests with pytest-bdd.

## Common Issues and Solutions

### Element Not Found Errors

**Error:**
```
ElementDoesNotExist: no elements could be found with css ".my-button"
```

**Solutions:**

1. **Check the selector:**
```python
# Try different selectors
browser.find_by_id('submit')
browser.find_by_name('submit')
browser.find_by_text('Submit')
browser.find_by_css('button[type="submit"]')
```

2. **Verify element exists:**
```python
# Check before accessing
if browser.is_element_present_by_css('.my-button'):
    browser.find_by_css('.my-button').first.click()
else:
    print("Button not found!")
    print(browser.html)  # Inspect HTML
```

3. **Add wait time:**
```python
# Wait for element to appear
assert browser.is_element_present_by_css('.my-button', wait_time=5)
```

4. **Check page loaded:**
```python
# Ensure navigation completed
@when("I visit the dashboard")
def visit_dashboard(browser, live_server):
    browser.visit(f'{live_server.url}/dashboard/')
    # Verify page loaded
    assert '/dashboard/' in browser.url
```

### Stale Object / Database Issues

**Error:**
```
The "Article" instance has been deleted, or its row is otherwise no longer available.
```

**Solution - Refresh from database:**
```python
@then("the article should be published")
def article_published(article):
    # Always refresh before assertions
    article.refresh_from_db()
    assert article.is_published
    assert article.published_at is not None
```

**Error:**
```
TransactionManagementError: An error occurred in the current transaction
```

**Solution - Check fixture scopes:**
```python
# Problem: session-scoped fixture with db access
@pytest.fixture(scope='session')
def sample_data(db):  # ❌ Won't work
    return User.objects.create(...)

# Solution: Use appropriate scope
@pytest.fixture(scope='function')  # ✅ Correct
def sample_data(db):
    return User.objects.create(...)
```

### Test Pollution / State Leakage

**Issue:** Tests pass individually but fail when run together.

**Solutions:**

1. **Check fixture scopes:**
```python
# Each test should get fresh data
@pytest.fixture(scope='function')  # Not 'module' or 'session'
def test_user(db):
    return User.objects.create_user(...)
```

2. **Verify database rollback:**
```python
# Add to conftest.py
@pytest.fixture(autouse=True)
def reset_db_sequences(db):
    """Ensure clean DB state."""
    yield
    # DB automatically rolled back by pytest-django
```

3. **Clear browser state:**
```python
@pytest.fixture
def browser(live_server):
    b = Browser('django')
    yield b
    # Cleanup
    b.cookies.delete()  # Clear cookies
    b.quit()
```

### Live Server Issues

**Error:**
```
requests.exceptions.ConnectionError: Connection refused
```

**Solutions:**

1. **Ensure live_server fixture used:**
```python
# ❌ Wrong
def visit_home(browser):
    browser.visit('http://localhost:8000/')

# ✅ Correct
def visit_home(browser, live_server):
    browser.visit(f'{live_server.url}/')
```

2. **Check ALLOWED_HOSTS:**
```python
# In test settings
ALLOWED_HOSTS = ['*', 'testserver']
```

3. **Port conflict:**
```python
# Use different port if needed
@pytest.fixture
def live_server():
    from pytest_django.live_server_helper import LiveServer
    server = LiveServer('127.0.0.1:8001')
    yield server
    server.stop()
```

### Import Errors

**Error:**
```
ModuleNotFoundError: No module named 'myapp'
```

**Solutions:**

1. **Check PYTHONPATH:**
```bash
# Run from project root
cd /path/to/django/project
pytest tests/

# Or set PYTHONPATH
export PYTHONPATH=/path/to/django/project:$PYTHONPATH
pytest
```

2. **Verify pytest.ini location:**
```bash
# pytest.ini should be in project root
myproject/
├── pytest.ini  # ← Here
├── manage.py
└── myapp/
```

3. **Check DJANGO_SETTINGS_MODULE:**
```ini
# In pytest.ini
[pytest]
DJANGO_SETTINGS_MODULE = myproject.settings.test
```

### Step Definition Not Found

**Error:**
```
StepDefinitionNotFoundError: Step definition is not found
```

**Solutions:**

1. **Import step definitions:**
```python
# In test file
from pytest_bdd import scenarios, given, when, then

# Import all scenarios from feature
scenarios('../features/my_feature.feature')

# Or specific scenario
from pytest_bdd import scenario
@scenario('../features/my_feature.feature', 'My scenario name')
def test_my_scenario():
    pass
```

2. **Check step text matches exactly:**
```gherkin
# In .feature file
When I click the submit button

# In step definition - MUST MATCH EXACTLY
@when("I click the submit button")  # ✅
@when("I click submit button")      # ❌ Missing "the"
```

3. **Use parsers for variable steps:**
```python
from pytest_bdd import parsers

@when(parsers.parse('I click the {button_name} button'))
def click_button(browser, button_name):
    browser.find_by_name(button_name).click()
```

### Scenario Not Collected

**Issue:** Scenarios not running.

**Solutions:**

1. **Check file naming:**
```bash
# ✅ Correct
test_login.py
login_test.py

# ❌ Wrong
login.py
steps_login.py
```

2. **Verify scenarios loaded:**
```python
# Make sure this is called
scenarios('../features/login.feature')

# Or for specific scenarios
from pytest_bdd import scenario

@scenario('../features/login.feature', 'Successful login')
def test_successful_login():
    pass
```

3. **Check feature file location:**
```python
# Relative path from step definition file
# If in: tests/acceptance/step_defs/test_login.py
# Feature in: tests/acceptance/features/login.feature
scenarios('../features/login.feature')  # ✅

# Or absolute path
scenarios('tests/acceptance/features/login.feature')
```

## Debugging Techniques

### 1. Add Breakpoints

```python
@when("I submit the form")
def submit_form(browser):
    import pdb; pdb.set_trace()  # Pause here
    browser.find_by_css('button').first.click()
```

In debugger:
```
(Pdb) browser.url  # Check current URL
(Pdb) browser.html  # View page HTML
(Pdb) browser.find_by_css('.error')  # Test selectors
```

### 2. Print HTML for Inspection

```python
@then("I should see an error")
def see_error(browser):
    print(browser.html)  # Run with: pytest -s
    assert browser.is_element_present_by_css('.error')
```

### 3. Print Current State

```python
@when("I click login")
def click_login(browser):
    print(f"Current URL: {browser.url}")
    print(f"Page title: {browser.title}")
    print(f"Cookies: {browser.cookies.all()}")
    browser.find_by_css('button').first.click()
```

### 4. Screenshot (Chrome/Firefox only)

```python
@then("I should see the dashboard")
def see_dashboard(browser):
    # Save screenshot on failure
    try:
        assert browser.is_text_present('Dashboard')
    except AssertionError:
        browser.driver.save_screenshot('failure.png')
        raise
```

### 5. Verbose Assertions

```python
# ❌ Uninformative
@then("the count should match")
def check_count(article):
    assert Article.objects.count() == 5

# ✅ Informative
@then("the count should match")
def check_count(article):
    count = Article.objects.count()
    assert count == 5, f"Expected 5 articles, found {count}"
```

### 6. Step-by-Step Verification

```python
@when("I submit the form")
def submit_form(browser):
    # Verify pre-conditions
    assert browser.is_element_present_by_css('form')

    # Perform action
    button = browser.find_by_css('button[type="submit"]').first
    assert button is not None, "Submit button not found"
    button.click()

    # Verify post-conditions
    print(f"After submit: {browser.url}")
```

## Performance Debugging

### Slow Tests

**Identify slow tests:**
```bash
# Show test durations
pytest --durations=10 tests/acceptance/

# Profile tests
pytest --profile tests/acceptance/
```

**Solutions:**

1. **Use Django driver instead of Chrome:**
```python
@pytest.fixture(scope='session')
def splinter_webdriver():
    return 'django'  # Much faster than 'chrome'
```

2. **Share expensive fixtures:**
```python
# Create once per session
@pytest.fixture(scope='session')
def base_categories(django_db_blocker):
    with django_db_blocker.unblock():
        Category.objects.create(name='Tech')
        Category.objects.create(name='Science')
```

3. **Disable migrations:**
```python
# In test settings
class DisableMigrations:
    def __contains__(self, item):
        return True
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()
```

4. **Tag slow tests:**
```python
# In feature file
@slow
Scenario: Complex workflow
```

```bash
# Skip slow tests during development
pytest -m "not slow"
```

## Django-Specific Debugging

### Check Database State

```python
@then("the user should exist")
def user_exists():
    from django.contrib.auth import get_user_model
    User = get_user_model()

    print(f"User count: {User.objects.count()}")
    print(f"Users: {list(User.objects.values('username', 'email'))}")

    assert User.objects.filter(email='test@example.com').exists()
```

### Check Email Sent

```python
@then("confirmation email sent")
def email_sent():
    from django.core.mail import outbox

    print(f"Emails sent: {len(outbox)}")
    for email in outbox:
        print(f"To: {email.to}")
        print(f"Subject: {email.subject}")
        print(f"Body: {email.body}")

    assert len(outbox) > 0
```

### Check Template Context

```python
# Only works with Django test client (not browser)
def test_article_list(client):
    response = client.get('/articles/')
    print(f"Context: {response.context}")
    print(f"Articles: {response.context['articles']}")
```

### Verify URL Routing

```python
@when("I visit the article page")
def visit_article(browser, live_server, article):
    from django.urls import reverse

    # Test URL reverse works
    url = reverse('article-detail', kwargs={'slug': article.slug})
    print(f"Resolved URL: {url}")

    browser.visit(f'{live_server.url}{url}')
```

## CI/CD Debugging

### GitHub Actions

```yaml
- name: Run tests with verbose output
  run: |
    pytest tests/acceptance/ -v -s --tb=short
```

### Save artifacts on failure

```yaml
- name: Run tests
  run: pytest tests/acceptance/

- name: Upload screenshots on failure
  if: failure()
  uses: actions/upload-artifact@v2
  with:
    name: test-screenshots
    path: screenshots/
```

## Helpful Commands

```bash
# Show what will be collected
pytest --collect-only tests/acceptance/

# Show available fixtures
pytest --fixtures

# Show test output in real-time
pytest -s tests/acceptance/

# Stop on first failure
pytest -x tests/acceptance/

# Run last failed tests
pytest --lf tests/acceptance/

# Run with specific marker
pytest -m smoke tests/acceptance/

# Run specific scenario by name
pytest -k "successful login" tests/acceptance/

# Verbose output with traceback
pytest -vv --tb=long tests/acceptance/
```

## When to Ask for Help

If you've tried:
1. Checking logs and error messages
2. Adding print statements
3. Using breakpoints
4. Verifying database state
5. Checking browser HTML
6. Running tests individually

And the issue persists, gather:
- Full error traceback
- Feature file content
- Step definition code
- Fixture definitions
- pytest.ini configuration
- Django settings (test)

Then search or ask for help with all this context.
