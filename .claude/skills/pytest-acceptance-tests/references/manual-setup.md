# Manual Django BDD Test Setup

Step-by-step guide to manually set up Django acceptance testing infrastructure.

## Installation

### 1. Install Required Packages

```bash
# Core packages
pip install pytest pytest-django pytest-bdd pytest-splinter

# Django driver dependencies
pip install splinter[django]

# Optional: For browser-based testing
pip install selenium webdriver-manager

# Create requirements-test.txt
cat > requirements-test.txt << EOF
pytest>=7.0.0
pytest-django>=4.5.0
pytest-bdd>=6.0.0
pytest-splinter>=3.3.0
splinter[django]>=0.19.0
EOF
```

### 2. Project Structure

Create directory structure:

```bash
# From Django project root
mkdir -p tests/acceptance/{features,step_defs}
touch tests/__init__.py
touch tests/acceptance/__init__.py
touch tests/acceptance/step_defs/__init__.py
```

Final structure:
```
myproject/
├── myapp/
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── acceptance/
│       ├── __init__.py
│       ├── conftest.py
│       ├── features/
│       └── step_defs/
│           └── __init__.py
├── pytest.ini
└── manage.py
```

## Configuration Files

### pytest.ini

Create `pytest.ini` in project root:

```ini
[pytest]
# Django settings module for tests
DJANGO_SETTINGS_MODULE = myproject.settings.test

# Test discovery patterns
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Where to look for tests
testpaths = tests

# Enable django-db for all tests (optional)
# Remove this if you want to be explicit about db access
# django_find_project = true

# Test markers for organization
markers =
    acceptance: Acceptance tests (BDD scenarios)
    smoke: Smoke tests (critical user journeys)
    slow: Slow-running tests
    integration: Integration tests
    unit: Unit tests
    django_db: Mark test as requiring database

# Additional pytest options
addopts =
    --strict-markers
    --reuse-db
    --nomigrations
    -v

# Ignore directories
norecursedirs = .git .tox dist build *.egg venv node_modules
```

### Test Settings

Create `myproject/settings/test.py`:

```python
"""Test-specific settings."""
from .base import *  # or from .settings import *

# Use in-memory SQLite for speed
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Faster password hashing
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable migrations for faster DB creation
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Simplified email
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Debug settings
DEBUG = False
TEMPLATE_DEBUG = False

# Allow all hosts for testing
ALLOWED_HOSTS = ['*', 'testserver']

# Remove debug toolbar if present
MIDDLEWARE = [m for m in MIDDLEWARE if 'debug_toolbar' not in m.lower()]

# Test media and static files
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_ROOT = os.path.join(BASE_DIR, 'test_media')
STATIC_ROOT = os.path.join(BASE_DIR, 'test_static')

# Simplify logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}
```

Update `pytest.ini` to use test settings:
```ini
DJANGO_SETTINGS_MODULE = myproject.settings.test
```

## Conftest Files

### Root conftest.py

Create `tests/conftest.py`:

```python
"""Root test configuration."""
import pytest
from django.core.management import call_command


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Custom database setup.
    Load fixtures or create test data here.
    """
    with django_db_blocker.unblock():
        # Example: Load fixtures
        # call_command('loaddata', 'test_data.json')
        pass


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Automatically enable database for all tests.
    Remove this if you prefer explicit db markers.
    """
    pass


@pytest.fixture
def api_client():
    """Django REST framework API client."""
    from rest_framework.test import APIClient
    return APIClient()
```

### Acceptance Tests conftest.py

Create `tests/acceptance/conftest.py`:

```python
"""Acceptance test configuration."""
import pytest
from splinter import Browser


@pytest.fixture(scope='session')
def splinter_webdriver():
    """Use Django test client for fast tests."""
    return 'django'


@pytest.fixture(scope='function')
def browser(live_server):
    """
    Browser instance using Django driver.

    For JavaScript-heavy features, change to:
        return 'chrome'  # or 'firefox'
    """
    b = Browser('django')
    b.base_url = live_server.url
    yield b
    b.quit()


@pytest.fixture
def authenticated_browser(browser, django_user_model, live_server):
    """Browser that's already logged in."""
    user = django_user_model.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )

    browser.visit(f'{live_server.url}/accounts/login/')
    browser.fill('username', 'testuser')
    browser.fill('password', 'testpass123')
    browser.find_by_css('button[type="submit"]').first.click()

    browser.current_user = user
    return browser


# Add your custom fixtures here
from django.contrib.auth import get_user_model
User = get_user_model()


@pytest.fixture
def sample_user(db):
    """Regular user for testing."""
    return User.objects.create_user(
        username='sampleuser',
        email='sample@example.com',
        password='samplepass123'
    )


@pytest.fixture
def admin_user(db):
    """Admin user for testing."""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )
```

## Browser Driver Configuration

### Django Driver (Default - Fast)

Already configured above. No additional setup needed.

### Chrome Driver (For JavaScript)

1. Install Chrome and chromedriver:

```bash
# macOS
brew install chromedriver

# Ubuntu
sudo apt-get install chromium-chromedriver

# Or use webdriver-manager (cross-platform)
pip install webdriver-manager
```

2. Update conftest.py:

```python
@pytest.fixture(scope='session')
def splinter_webdriver():
    return 'chrome'

@pytest.fixture(scope='session')
def splinter_driver_kwargs():
    """Chrome options."""
    from selenium.webdriver.chrome.options import Options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run without GUI
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    return {'options': chrome_options}
```

### Firefox Driver

```python
@pytest.fixture(scope='session')
def splinter_webdriver():
    return 'firefox'

@pytest.fixture(scope='session')
def splinter_driver_kwargs():
    """Firefox options."""
    from selenium.webdriver.firefox.options import Options
    firefox_options = Options()
    firefox_options.add_argument('--headless')
    return {'options': firefox_options}
```

## First Feature and Test

### 1. Create Feature File

Create `tests/acceptance/features/homepage.feature`:

```gherkin
Feature: Homepage
  As a visitor
  I want to view the homepage
  So that I can learn about the site

  Scenario: View homepage
    Given I am on the homepage
    Then I should see the site title
    And I should see the navigation menu
```

### 2. Create Step Definitions

Create `tests/acceptance/step_defs/test_homepage.py`:

```python
"""Homepage step definitions."""
import pytest
from pytest_bdd import scenarios, given, when, then

# Load all scenarios from homepage.feature
scenarios('../features/homepage.feature')


@given("I am on the homepage")
def on_homepage(browser, live_server):
    """Navigate to homepage."""
    browser.visit(live_server.url)


@then("I should see the site title")
def see_site_title(browser):
    """Verify site title present."""
    assert browser.is_element_present_by_css('h1')


@then("I should see the navigation menu")
def see_nav_menu(browser):
    """Verify navigation present."""
    assert browser.is_element_present_by_css('nav')
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Only Acceptance Tests

```bash
pytest tests/acceptance/
```

### Run Specific Feature

```bash
pytest tests/acceptance/step_defs/test_homepage.py
```

### Run with Markers

```bash
# Run smoke tests
pytest -m smoke

# Run acceptance tests
pytest -m acceptance

# Run non-slow tests
pytest -m "not slow"
```

### Verbose Output

```bash
pytest -v tests/acceptance/
```

### Show Print Statements

```bash
pytest -s tests/acceptance/
```

### Stop on First Failure

```bash
pytest -x tests/acceptance/
```

## Troubleshooting

### Tests Not Found

Check:
1. File naming: `test_*.py` or `*_test.py`
2. Function naming: `test_*`
3. `__init__.py` in all test directories
4. `pytest.ini` testpaths setting

### Database Errors

Ensure:
1. `@pytest.mark.django_db` on tests (or autouse fixture)
2. `DJANGO_SETTINGS_MODULE` in pytest.ini
3. Test database permissions
4. Migrations applied (or disabled in test settings)

### Import Errors

Check:
1. Django project on Python path
2. Test settings importable
3. All required packages installed
4. Virtual environment activated

### Live Server Not Starting

Verify:
1. `live_server` fixture used in browser fixture
2. No port conflicts
3. ALLOWED_HOSTS includes 'testserver'
4. Django configured correctly

### Browser Issues

For Django driver:
- Check splinter[django] installed
- Verify lxml and cssselect installed

For Chrome/Firefox:
- Check browser installed
- Verify driver (chromedriver/geckodriver) installed
- Check driver is in PATH

## CI/CD Integration

### GitHub Actions

`.github/workflows/tests.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-test.txt

    - name: Run tests
      run: |
        pytest tests/acceptance/ -v
```

### GitLab CI

`.gitlab-ci.yml`:

```yaml
test:
  image: python:3.11

  before_script:
    - pip install -r requirements.txt
    - pip install -r requirements-test.txt

  script:
    - pytest tests/acceptance/ -v
```

## Next Steps

1. Write your first feature file
2. Implement step definitions
3. Add custom fixtures for your models
4. Set up CI/CD pipeline
5. Gradually add more acceptance tests

See `references/gherkin-patterns.md` and `references/step-patterns.md` for examples.
