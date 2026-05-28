#!/usr/bin/env python3
"""Setup Django BDD Test Infrastructure

Creates directory structure, configuration files, and fixtures
for Django acceptance testing with pytest-bdd.

Usage:
    python setup_django_bdd.py --project-root /path/to/django/project
    python setup_django_bdd.py --project-root . --settings-module myproject.settings
"""

import argparse
import sys
from pathlib import Path


def create_directory_structure(project_root):
    """Create test directory structure."""
    test_dirs = [
        "tests",
        "tests/acceptance",
        "tests/acceptance/features",
        "tests/acceptance/step_defs",
    ]

    for dir_path in test_dirs:
        full_path = project_root / dir_path
        full_path.mkdir(parents=True, exist_ok=True)

        # Create __init__.py files
        if dir_path.startswith("tests"):
            init_file = full_path / "__init__.py"
            if not init_file.exists():
                init_file.write_text('"""Test package."""\n')

        print(f"✓ Created {dir_path}/")


def create_pytest_ini(project_root, settings_module):
    """Create pytest.ini configuration."""
    pytest_ini = project_root / "pytest.ini"

    if pytest_ini.exists():
        print(f"! pytest.ini already exists at {pytest_ini}")
        response = input("  Overwrite? (y/N): ")
        if response.lower() != "y":
            print("  Skipped pytest.ini")
            return

    content = f"""[pytest]
# Django settings
DJANGO_SETTINGS_MODULE = {settings_module}.test
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Test discovery
testpaths = tests

# pytest-django settings
django_find_project = true

# Markers for test organization
markers =
    acceptance: Acceptance tests (BDD scenarios)
    smoke: Smoke tests (critical paths)
    slow: Slow-running tests
    integration: Integration tests
    unit: Unit tests
    django_db: Tests requiring database access

# pytest options
addopts =
    --strict-markers
    --reuse-db
    --nomigrations
    -v

# Ignore directories
norecursedirs = .git .tox dist build *.egg venv node_modules
"""

    pytest_ini.write_text(content)
    print("✓ Created pytest.ini")


def create_root_conftest(project_root):
    """Create root conftest.py."""
    conftest = project_root / "tests" / "conftest.py"

    if conftest.exists():
        print("! tests/conftest.py already exists")
        return

    content = '''"""Root test configuration."""
import pytest
from django.core.management import call_command


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Custom database setup for tests.
    Load fixtures, create initial data, etc.
    """
    with django_db_blocker.unblock():
        # Example: Load fixtures
        # call_command('loaddata', 'test_data.json')
        pass


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Automatically enable database access for all tests.
    Remove this if you want to be explicit about db access.
    """
    pass


@pytest.fixture
def api_client():
    """Provide Django REST framework API client if installed."""
    try:
        from rest_framework.test import APIClient
        return APIClient()
    except ImportError:
        pytest.skip("DRF not installed")
'''

    conftest.write_text(content)
    print("✓ Created tests/conftest.py")


def create_acceptance_conftest(project_root):
    """Create acceptance test conftest.py."""
    conftest = project_root / "tests" / "acceptance" / "conftest.py"

    if conftest.exists():
        print("! tests/acceptance/conftest.py already exists")
        return

    content = '''"""Acceptance test configuration."""
import pytest
from splinter import Browser


@pytest.fixture(scope='session')
def splinter_webdriver():
    """
    Use Django test client driver for fast tests.

    For JavaScript-heavy features, change to:
        return 'chrome'  # or 'firefox'
    """
    return 'django'


@pytest.fixture(scope='function')
def browser(live_server):
    """
    Provide browser instance using Django driver.

    Function-scoped to ensure clean state between tests.
    """
    b = Browser('django')
    b.base_url = live_server.url
    yield b
    b.quit()


@pytest.fixture
def authenticated_browser(browser, django_user_model, live_server):
    """Provide a browser that's already logged in."""
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


# Custom fixtures for your Django models
from django.contrib.auth import get_user_model
User = get_user_model()


@pytest.fixture
def sample_user(db):
    """Create a regular user."""
    return User.objects.create_user(
        username='sampleuser',
        email='sample@example.com',
        password='samplepass123'
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )
'''

    conftest.write_text(content)
    print("✓ Created tests/acceptance/conftest.py")


def create_test_settings(project_root, settings_module):
    """Create test settings file."""
    # Extract project name and settings location
    parts = settings_module.split(".")
    if len(parts) == 2:
        # myproject.settings
        project_name = parts[0]
        settings_dir = project_root / project_name
    else:
        # myproject.settings.base
        project_name = parts[0]
        settings_dir = project_root / project_name / "settings"

    test_settings = settings_dir / "test.py"

    if test_settings.exists():
        print(f"! {test_settings} already exists")
        return

    # Determine base import
    base_import = "from .base import *" if (settings_dir / "base.py").exists() else "from .settings import *"

    content = f'''"""Test-specific Django settings."""
{base_import}

# Use in-memory SQLite for speed
DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }}
}}

# Faster password hashing
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable migrations for faster test database creation
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Simplified email backend
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Debug settings
DEBUG = False
TEMPLATE_DEBUG = False

# Allow all hosts for testing
ALLOWED_HOSTS = ['*', 'testserver']

# Remove debug toolbar and unnecessary middleware
MIDDLEWARE = [m for m in MIDDLEWARE if 'debug' not in m.lower()]

# Test media and static files
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_ROOT = os.path.join(BASE_DIR, 'test_media')
STATIC_ROOT = os.path.join(BASE_DIR, 'test_static')

# Simplified logging
LOGGING = {{
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {{
        'console': {{
            'class': 'logging.StreamHandler',
        }},
    }},
    'root': {{
        'handlers': ['console'],
        'level': 'WARNING',
    }},
}}
'''

    settings_dir.mkdir(parents=True, exist_ok=True)
    test_settings.write_text(content)
    print(f"✓ Created {test_settings}")


def create_example_feature(project_root):
    """Create example feature file."""
    feature_file = project_root / "tests" / "acceptance" / "features" / "example.feature"

    if feature_file.exists():
        print("! example.feature already exists")
        return

    content = """Feature: Homepage
  As a visitor
  I want to view the homepage
  So that I can learn about the site

  Scenario: View homepage
    Given I am on the homepage
    Then I should see the page title
    And I should see the navigation menu
"""

    feature_file.write_text(content)
    print("✓ Created example.feature")


def create_example_steps(project_root):
    """Create example step definitions."""
    steps_file = project_root / "tests" / "acceptance" / "step_defs" / "test_example.py"

    if steps_file.exists():
        print("! test_example.py already exists")
        return

    content = '''"""Example step definitions."""
from pytest_bdd import scenarios, given, when, then

# Load all scenarios from example.feature
scenarios('../features/example.feature')


@given("I am on the homepage")
def on_homepage(browser, live_server):
    """Navigate to homepage."""
    browser.visit(live_server.url)


@then("I should see the page title")
def see_title(browser):
    """Verify page title present."""
    # Customize this assertion for your site
    assert browser.title is not None


@then("I should see the navigation menu")
def see_navigation(browser):
    """Verify navigation present."""
    # Customize this selector for your site
    assert browser.is_element_present_by_css('nav') or \\
           browser.is_element_present_by_css('header')
'''

    steps_file.write_text(content)
    print("✓ Created test_example.py")


def create_requirements(project_root):
    """Create requirements-test.txt."""
    req_file = project_root / "requirements-test.txt"

    if req_file.exists():
        print("! requirements-test.txt already exists")
        return

    content = """# Testing dependencies
pytest>=7.0.0
pytest-django>=4.5.0
pytest-bdd>=6.0.0
pytest-splinter>=3.3.0
splinter[django]>=0.19.0

# Optional: For browser-based testing
# selenium>=4.0.0
# webdriver-manager>=3.8.0
"""

    req_file.write_text(content)
    print("✓ Created requirements-test.txt")


def create_readme(project_root):
    """Create README for tests."""
    readme = project_root / "tests" / "README.md"

    if readme.exists():
        print("! tests/README.md already exists")
        return

    content = """# Django Acceptance Tests

Acceptance tests for this Django project using pytest-bdd and pytest-splinter.

## Setup

Install test dependencies:

```bash
pip install -r requirements-test.txt
```

## Running Tests

```bash
# Run all acceptance tests
pytest tests/acceptance/

# Run specific feature
pytest tests/acceptance/step_defs/test_example.py

# Run with verbose output
pytest -v tests/acceptance/

# Run and show print statements
pytest -s tests/acceptance/

# Run tests with marker
pytest -m smoke
```

## Writing Tests

1. **Create feature file** in `tests/acceptance/features/`
2. **Write scenarios** using Gherkin syntax
3. **Implement step definitions** in `tests/acceptance/step_defs/`
4. **Run tests** with pytest

## Directory Structure

```
tests/
├── acceptance/
│   ├── conftest.py       # Acceptance test fixtures
│   ├── features/         # Gherkin feature files
│   │   └── example.feature
│   └── step_defs/        # Step implementations
│       └── test_example.py
└── conftest.py           # Root fixtures
```

## Useful Resources

- [pytest-bdd Documentation](https://pytest-bdd.readthedocs.io/)
- [pytest-splinter Documentation](https://github.com/pytest-dev/pytest-splinter)
- [Splinter Documentation](https://splinter.readthedocs.io/)
"""

    readme.write_text(content)
    print("✓ Created tests/README.md")


def main():
    parser = argparse.ArgumentParser(description="Setup Django BDD test infrastructure")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Django project root directory (default: current directory)",
    )
    parser.add_argument(
        "--settings-module",
        help="Django settings module (e.g., myproject.settings). Will be auto-detected if not provided.",
    )

    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()

    # Verify this is a Django project
    if not (project_root / "manage.py").exists():
        print(f"ERROR: No manage.py found in {project_root}")
        print("Please run from Django project root or specify --project-root")
        sys.exit(1)

    # Auto-detect settings module if not provided
    settings_module = args.settings_module
    if not settings_module:
        # Try to find settings module
        for item in project_root.iterdir():
            if item.is_dir() and (item / "settings.py").exists():
                settings_module = f"{item.name}.settings"
                break
            if item.is_dir() and (item / "settings" / "base.py").exists():
                settings_module = f"{item.name}.settings.base"
                break

        if not settings_module:
            print("ERROR: Could not auto-detect settings module")
            print("Please specify --settings-module")
            sys.exit(1)

    print(f"\nSetting up Django BDD tests in: {project_root}")
    print(f"Using settings module: {settings_module}\n")

    # Create structure
    create_directory_structure(project_root)
    create_pytest_ini(project_root, settings_module)
    create_root_conftest(project_root)
    create_acceptance_conftest(project_root)
    create_test_settings(project_root, settings_module)
    create_example_feature(project_root)
    create_example_steps(project_root)
    create_requirements(project_root)
    create_readme(project_root)

    print("\n✓ Setup complete!")
    print("\nNext steps:")
    print("  1. Install dependencies: pip install -r requirements-test.txt")
    print("  2. Run example test: pytest tests/acceptance/step_defs/test_example.py")
    print("  3. Customize tests/acceptance/conftest.py for your models")
    print("  4. Write your feature files and step definitions\n")


if __name__ == "__main__":
    main()
